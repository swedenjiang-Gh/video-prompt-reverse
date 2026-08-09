"""Fuse separated observations into a strict prompt package."""

import argparse
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

try:
    from scripts.validate_prompt_package import (
        dumps_strict_json,
        load_strict_json,
        loads_strict_json,
        PROMPT_PACKAGE_CONTRACT,
        reject_sensitive_content,
        validate_prompt_package,
    )
except ModuleNotFoundError:  # Direct script execution.
    from validate_prompt_package import (
        dumps_strict_json,
        load_strict_json,
        loads_strict_json,
        PROMPT_PACKAGE_CONTRACT,
        reject_sensitive_content,
        validate_prompt_package,
    )

SOURCE_NAMESPACES = tuple(PROMPT_PACKAGE_CONTRACT["objects"]["sources"])
PROMPT_SECTIONS = tuple(PROMPT_PACKAGE_CONTRACT["prompt_format"]["ordered_sections"])
PROMPT_ATOM_FIELDS = {
    "text",
    "source_stream",
    "source_ref",
    "source_quote",
    "evidence_refs",
    "status",
}
Runner = Callable[[str, str], str]
FUSION_STAGES = ("base", "i2v", "enhanced", "variants")
VARIANT_DIMENSIONS = ("camera_motion", "lighting", "timing")


def load_records(path: Path) -> list[dict]:
    """Load a JSON object/array or JSONL records from a local observation file."""
    raw = path.read_text(encoding="utf-8")
    try:
        parsed = loads_strict_json(raw)
    except ValueError:
        lines = [line for line in raw.splitlines() if line.strip()]
        if len(lines) < 2:
            raise
        try:
            parsed = [loads_strict_json(line) for line in lines]
        except ValueError:
            raise ValueError("observation input must be strict JSON or JSONL") from None
    records = parsed if isinstance(parsed, list) else [parsed]
    if any(not isinstance(record, dict) for record in records):
        raise ValueError("observation input must contain JSON objects")
    return records


def build_source_references(source_inputs: dict[str, list[dict]]) -> dict[str, list[str]]:
    """Assign deterministic, namespace-bound references without exposing source content."""
    if set(source_inputs) != set(SOURCE_NAMESPACES):
        raise ValueError("source inputs require exactly four namespaces")
    references = {}
    for namespace in SOURCE_NAMESPACES:
        records = source_inputs[namespace]
        if not isinstance(records, list):
            raise ValueError(f"{namespace} source input must be a list")
        references[namespace] = [
            f"{namespace}:{index:04d}" for index in range(1, len(records) + 1)
        ]
    return references


def build_fusion_instruction(
    *,
    evidence_manifest: dict,
    skycaptioner: list[dict],
    general_vlm: list[dict],
    asr_ocr: list[dict],
    human_context: list[dict],
    target_engine: dict,
    mode: str,
    generated_at: str,
) -> str:
    """Build a deterministic instruction without pre-merging source streams."""
    sources = {
        "skycaptioner": skycaptioner,
        "general_vlm": general_vlm,
        "asr_ocr": asr_ocr,
        "human_context": human_context,
    }
    return "\n".join(
        (
            "Use only the four named source namespaces and keep them separate.",
            "Represent each section as a non-empty array of prompt-atom objects with exactly text, source_stream, source_ref, source_quote, evidence_refs, and status.",
            "Do not put semicolons in atom text and do not combine independently attributable facts in one atom.",
            "A source-supported atom text must contain its exact source_quote, name one required source_ref, and copy matching evidence_refs from that source record.",
            "A conservative-inferred or creative atom must use source_stream none, null source_ref/source_quote, empty evidence_refs, and include its owner-local label in text.",
            "Do not emit credentials, private machine roots, model paths, or parameter flags in prompt prose.",
            "PACKAGE_METADATA_JSON",
            dumps_strict_json(
                {"mode": mode, "generated_at": generated_at},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "END_PACKAGE_METADATA_JSON",
            "EVIDENCE_MANIFEST_JSON",
            dumps_strict_json(
                evidence_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
            "END_EVIDENCE_MANIFEST_JSON",
            "SOURCE_INPUTS_JSON",
            dumps_strict_json(
                sources, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
            "END_SOURCE_INPUTS_JSON",
            "TARGET_ENGINE_JSON",
            dumps_strict_json(
                target_engine, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
            "END_TARGET_ENGINE_JSON",
        )
    )


def build_fusion_stage_instruction(
    stage: str, common_instruction: str, baseline_t2v: dict | None = None
) -> str:
    """Constrain one model call to a small stage-owned JSON object."""
    if stage not in FUSION_STAGES:
        raise ValueError("unknown fusion stage")
    section_names = ", ".join(PROMPT_SECTIONS)
    contracts = {
        "base": (
            "Return exactly five top-level fields: five_role_review, reconstruction_t2v, "
            "anchors, negative_constraints, uncertainties. five_role_review has exactly "
            "screenwriter, director, cinematographer, production_designer, editor as non-empty "
            "strings. reconstruction_t2v has exactly the eight canonical sections. anchors is "
            "a non-empty list of factual continuity statements, never file paths. "
            "negative_constraints has exactly reconstruction_source and generation_stability as "
            "non-empty lists of actual prohibitions, never file paths. uncertainties is a list "
            "of uncertainty statements. Do not output metadata, media, shots, sources, prompts, "
            "engine, attribution, or any other field."
        ),
        "i2v": (
            "Return exactly one top-level field reconstruction_i2v containing exactly the eight "
            "canonical sections. Make it a complete I2V prompt; do not copy model-independent "
            "package fields and do not output attribution."
        ),
        "enhanced": (
            "Return exactly one top-level field enhanced containing exactly the eight canonical "
            "sections. Preserve source-backed identity and continuity while making enhancements "
            "explicitly conservative-inferred or creative. Do not output attribution."
        ),
        "variants": (
            "Return exactly camera_motion, lighting, and timing. Each value is only a non-empty "
            "array of prompt-atom objects replacing respectively CAMERA, LIGHTING, and TIMING in "
            "the supplied baseline. Do not repeat the other seven sections and do not output "
            "changed_dimension, complete prompts, or attribution."
        ),
    }
    parts = [
        "FUSION_STAGE",
        stage,
        "STAGE_OUTPUT_CONTRACT",
        contracts[stage],
        f"CANONICAL_SECTIONS: {section_names}",
        "END_STAGE_OUTPUT_CONTRACT",
    ]
    if stage != "base":
        if baseline_t2v is None:
            raise ValueError("later fusion stages require the baseline T2V draft")
        parts.extend(
            (
                "BASELINE_T2V_JSON",
                dumps_strict_json(
                    baseline_t2v,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "END_BASELINE_T2V_JSON",
            )
        )
    parts.extend(("COMMON_FUSION_CONTEXT", common_instruction, "END_COMMON_FUSION_CONTEXT"))
    return "\n".join(parts)


def extract_strict_json_object(raw_output: str) -> dict:
    """Accept only one bare JSON object, with no model commentary or fences."""
    try:
        package = loads_strict_json(raw_output)
    except ValueError:
        raise ValueError("model output must contain exactly one JSON object") from None
    if not isinstance(package, dict):
        raise ValueError("model output must contain exactly one JSON object")
    return package


def normalize_fusion_draft(draft: dict) -> dict:
    """Render structured model atoms into final prompt strings and attribution rows."""
    expected_top_level = set(PROMPT_PACKAGE_CONTRACT["objects"]["prompt_package"]) - {
        "attribution"
    }
    if not isinstance(draft, dict) or set(draft) != expected_top_level:
        raise ValueError("fusion draft has invalid top-level fields")
    prompts = draft.get("prompts")
    expected_prompt_fields = set(PROMPT_PACKAGE_CONTRACT["objects"]["prompts"])
    if not isinstance(prompts, dict) or set(prompts) != expected_prompt_fields:
        raise ValueError("fusion draft has invalid prompt fields")

    attribution_entries = []

    def render_prompt(prompt_name: str, value: object) -> str:
        if not isinstance(value, dict) or set(value) != set(PROMPT_SECTIONS):
            raise ValueError(f"{prompt_name} prompt sections must be exactly canonical")
        lines = []
        for section in PROMPT_SECTIONS:
            atoms = value[section]
            if not isinstance(atoms, list) or not atoms:
                raise ValueError(f"{prompt_name}.{section} requires prompt atoms")
            atom_texts = []
            for atom_index, atom in enumerate(atoms, start=1):
                if not isinstance(atom, dict) or set(atom) != PROMPT_ATOM_FIELDS:
                    raise ValueError(f"{prompt_name}.{section} has an invalid prompt atom")
                text = atom["text"]
                if not isinstance(text, str) or not text.strip() or ";" in text:
                    raise ValueError(f"{prompt_name}.{section} atom text must be non-empty and atomic")
                text = text.strip()
                atom_texts.append(text)
                attribution_entries.append(
                    {
                        "fact_id": f"fact-{len(attribution_entries) + 1:04d}",
                        "prompt_ref": f"{prompt_name}.{section}.{atom_index:03d}",
                        "atom": text,
                        "owner_section": section,
                        "source_stream": atom["source_stream"],
                        "source_ref": atom["source_ref"],
                        "source_quote": atom["source_quote"],
                        "evidence_refs": atom["evidence_refs"],
                        "status": atom["status"],
                    }
                )
            lines.append(f"{section}: {'; '.join(atom_texts)}")
        return "\n".join(lines)

    final_prompts = {
        "reconstruction_t2v": render_prompt(
            "reconstruction_t2v", prompts["reconstruction_t2v"]
        ),
        "reconstruction_i2v": render_prompt(
            "reconstruction_i2v", prompts["reconstruction_i2v"]
        ),
        "enhanced": render_prompt("enhanced", prompts["enhanced"]),
        "single_variable_variants": [],
    }
    variants = prompts["single_variable_variants"]
    if not isinstance(variants, list):
        raise ValueError("fusion draft variants must be a list")
    expected_variant_fields = set(
        PROMPT_PACKAGE_CONTRACT["objects"]["single_variable_variant"]
    )
    for index, variant in enumerate(variants, start=1):
        if not isinstance(variant, dict) or set(variant) != expected_variant_fields:
            raise ValueError("fusion draft has an invalid variant")
        final_prompts["single_variable_variants"].append(
            {
                "changed_dimension": variant["changed_dimension"],
                "prompt": render_prompt(f"variant_{index}", variant["prompt"]),
            }
        )

    package = dict(draft)
    package["prompts"] = final_prompts
    package["attribution"] = {
        "status": "source-closed",
        "entries": attribution_entries,
    }
    return package


def _string_leaves(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _string_leaves(child)
    elif isinstance(value, list):
        for child in value:
            yield from _string_leaves(child)


def _record_evidence_refs(record: object) -> set[str]:
    references = set()
    if isinstance(record, dict):
        for name, value in record.items():
            if name == "evidence_refs" and isinstance(value, list):
                references.update(item for item in value if isinstance(item, str) and item)
            elif name == "path" and isinstance(value, str) and value:
                references.add(value)
            else:
                references.update(_record_evidence_refs(value))
    elif isinstance(record, list):
        for value in record:
            references.update(_record_evidence_refs(value))
    return references


def _label_atom(atom: dict, status: str) -> dict:
    label = "creative choice" if status == "creative" else "conservative inferred choice"
    text = atom.get("text", "")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("prompt atom text must be non-empty")
    text = text.strip()
    if label not in text.casefold():
        text = f"{label}: {text}"
    return {
        "text": text,
        "source_stream": "none",
        "source_ref": None,
        "source_quote": None,
        "evidence_refs": [],
        "status": status,
    }


def canonicalize_prompt_draft(
    prompt: dict, source_inputs: dict[str, list[dict]], required_sources: dict[str, list[str]]
) -> dict:
    """Keep source support only when the atom closes against the named source record."""
    _require_section_draft(prompt, "prompt")
    source_records = {}
    for namespace, records in source_inputs.items():
        references = required_sources.get(namespace, [])
        if isinstance(records, list) and isinstance(references, list):
            source_records.update(zip(references, records, strict=False))

    canonical = {}
    for section in PROMPT_SECTIONS:
        canonical[section] = []
        for atom in prompt[section]:
            if not isinstance(atom, dict) or set(atom) != PROMPT_ATOM_FIELDS:
                raise ValueError(f"prompt.{section} has an invalid prompt atom")
            status = atom.get("status")
            if status == "creative":
                canonical[section].append(_label_atom(atom, "creative"))
                continue
            if status == "conservative-inferred":
                canonical[section].append(_label_atom(atom, "conservative-inferred"))
                continue

            text = atom.get("text")
            namespace = atom.get("source_stream")
            source_ref = atom.get("source_ref")
            source_quote = atom.get("source_quote")
            evidence_refs = atom.get("evidence_refs")
            record = source_records.get(source_ref)
            available_evidence = (
                _record_evidence_refs(record) if isinstance(record, dict) else set()
            )
            support_closes = (
                status in {"supported", "source-supported"}
                and isinstance(text, str)
                and bool(text.strip())
                and namespace in required_sources
                and isinstance(source_ref, str)
                and source_ref in required_sources.get(namespace, [])
                and isinstance(record, dict)
                and isinstance(source_quote, str)
                and bool(source_quote.strip())
                and source_quote.casefold() in text.casefold()
                and any(
                    source_quote.casefold() in leaf.casefold()
                    for leaf in _string_leaves(record)
                )
                and isinstance(evidence_refs, list)
                and all(isinstance(reference, str) for reference in evidence_refs)
                and (
                    not available_evidence
                    or (bool(evidence_refs) and set(evidence_refs).issubset(available_evidence))
                )
            )
            if support_closes:
                supported_atom = deepcopy(atom)
                supported_atom["text"] = text.strip()
                supported_atom["status"] = "source-supported"
                canonical[section].append(supported_atom)
            else:
                canonical[section].append(_label_atom(atom, "conservative-inferred"))
    return canonical


def _canonicalize_negative_constraints(value: object) -> dict:
    defaults = {
        "reconstruction_source": [
            "Do not invent subjects, dialogue, readable text, objects, locations, actions, or shot order absent from accepted source evidence.",
            "Do not alter source-supported identity, wardrobe, props, palette, composition, or confirmed on-screen text.",
        ],
        "generation_stability": [
            "Avoid identity drift, wardrobe drift, prop deformation, anatomy errors, temporal flicker, unintended scene cuts, and unstable text.",
            "Avoid duplicated subjects, warped hands or faces, floating objects, inconsistent lighting, and camera motion that breaks continuity.",
        ],
    }
    if not isinstance(value, dict) or set(value) != set(defaults):
        return defaults
    result = deepcopy(value)
    reconstruction = result["reconstruction_source"]
    reconstruction_text = " ".join(reconstruction).casefold() if isinstance(reconstruction, list) else ""
    implementation_terms = (
        "file path",
        "credential",
        "attribution field",
        "media, shots, sources",
        "prompt field",
        "engine field",
    )
    if (
        not isinstance(reconstruction, list)
        or not reconstruction
        or any(not isinstance(item, str) or not item.strip() for item in reconstruction)
        or any(term in reconstruction_text for term in implementation_terms)
    ):
        result["reconstruction_source"] = defaults["reconstruction_source"]
    stability = result["generation_stability"]
    stability_text = " ".join(stability).casefold() if isinstance(stability, list) else ""
    stability_terms = ("drift", "flicker", "anatom", "deform", "warp", "duplicate", "continuity")
    if (
        not isinstance(stability, list)
        or not stability
        or any(not isinstance(item, str) or not item.strip() for item in stability)
        or not any(term in stability_text for term in stability_terms)
    ):
        result["generation_stability"] = defaults["generation_stability"]
    return result


def _semantic_prompt_text(prompt: dict) -> tuple[str, ...]:
    labels = ("creative choice:", "conservative inferred choice:")
    values = []
    for section in PROMPT_SECTIONS:
        for atom in prompt[section]:
            text = atom["text"].strip().casefold()
            for label in labels:
                if text.startswith(label):
                    text = text[len(label):].strip()
            values.append(text)
    return tuple(values)


def _require_stage_fields(value: object, fields: set[str], stage: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{stage} fusion stage has invalid fields")
    return value


def _require_section_draft(value: object, location: str) -> dict:
    if not isinstance(value, dict) or set(value) != set(PROMPT_SECTIONS):
        raise ValueError(f"{location} prompt sections must be exactly canonical")
    for section in PROMPT_SECTIONS:
        atoms = value[section]
        if not isinstance(atoms, list) or not atoms:
            raise ValueError(f"{location}.{section} requires prompt atoms")
    return value


def validate_fusion_stage_output(stage: str, output: object) -> dict:
    """Reject extra, missing, or null stage content before the next model call."""
    if stage == "base":
        output = _require_stage_fields(
            output,
            {
                "five_role_review",
                "reconstruction_t2v",
                "anchors",
                "negative_constraints",
                "uncertainties",
            },
            stage,
        )
        _require_section_draft(output["reconstruction_t2v"], "reconstruction_t2v")
    elif stage == "i2v":
        output = _require_stage_fields(output, {"reconstruction_i2v"}, stage)
        _require_section_draft(output["reconstruction_i2v"], "reconstruction_i2v")
    elif stage == "enhanced":
        output = _require_stage_fields(output, {"enhanced"}, stage)
        _require_section_draft(output["enhanced"], "enhanced")
    elif stage == "variants":
        output = _require_stage_fields(output, set(VARIANT_DIMENSIONS), stage)
        for dimension in VARIANT_DIMENSIONS:
            if not isinstance(output[dimension], list) or not output[dimension]:
                raise ValueError(f"variants.{dimension} requires prompt atoms")
    else:
        raise ValueError("unknown fusion stage")
    return output


def _fixed_package_fields(
    *,
    evidence_manifest: dict,
    general_vlm: list[dict],
    required_sources: dict,
    target_engine: dict,
    mode: str,
    generated_at: str,
) -> dict:
    """Copy facts already owned by deterministic inputs instead of asking the model."""
    manifest_media = evidence_manifest.get("media", {})
    descriptions = {
        record.get("shot_id"): record.get("observation")
        for record in general_vlm
        if isinstance(record, dict)
        and isinstance(record.get("shot_id"), str)
        and isinstance(record.get("observation"), str)
        and record["observation"].strip()
    }
    shots = []
    for manifest_shot in evidence_manifest.get("shots", []):
        shot_id = manifest_shot.get("id")
        description = descriptions.get(shot_id)
        if not description:
            raise ValueError(f"general_vlm requires one observation for {shot_id}")
        shots.append(
            {
                "id": shot_id,
                "timestamps": deepcopy(manifest_shot.get("timestamps")),
                "evidence_refs": [item["path"] for item in manifest_shot.get("evidence", [])],
                "description": description,
            }
        )
    engine = {
        "name": target_engine.get("name"),
        "parameters": deepcopy(target_engine.get("parameters")),
        "compatibility_notes": deepcopy(target_engine.get("compatibility_notes", [])),
    }
    return {
        "metadata": {"mode": mode, "generated_at": generated_at},
        "media": {
            name: manifest_media.get(name)
            for name in ("duration_seconds", "width", "height", "fps")
        },
        "shots": shots,
        "sources": deepcopy(required_sources),
        "engine": engine,
    }


def assemble_staged_fusion(
    *,
    stage_outputs: dict[str, dict],
    evidence_manifest: dict,
    source_inputs: dict[str, list[dict]],
    required_sources: dict,
    target_engine: dict,
    mode: str,
    generated_at: str,
) -> dict:
    """Build the full draft without giving the model control of fixed fields or copied variants."""
    if set(stage_outputs) != set(FUSION_STAGES):
        raise ValueError("fusion requires exactly four completed stages")
    for stage in FUSION_STAGES:
        validate_fusion_stage_output(stage, stage_outputs[stage])
    base = stage_outputs["base"]
    baseline = canonicalize_prompt_draft(
        base["reconstruction_t2v"], source_inputs, required_sources
    )
    reconstruction_i2v = canonicalize_prompt_draft(
        stage_outputs["i2v"]["reconstruction_i2v"], source_inputs, required_sources
    )
    enhanced = canonicalize_prompt_draft(
        stage_outputs["enhanced"]["enhanced"], source_inputs, required_sources
    )
    if _semantic_prompt_text(reconstruction_i2v) == _semantic_prompt_text(baseline):
        first_frame = evidence_manifest.get("shots", [{}])[0].get("evidence", [{}])[0].get("path")
        frame_role = (
            f"Use the approved task-local first frame {first_frame} as the binding identity, wardrobe, palette, and composition reference while animating only source-supported motion."
            if isinstance(first_frame, str) and first_frame
            else "No approved first-frame image was supplied, so do not claim image-locked identity or composition control."
        )
        reconstruction_i2v["CONSTRAINTS"].append(
            _label_atom({"text": frame_role}, "creative")
        )
    if enhanced == baseline:
        enhanced["ACTION"].append(
            _label_atom(
                {
                    "text": "Intensify the action into a clearer setup, acceleration, and graphic payoff while preserving source-backed identity and scene order."
                },
                "creative",
            )
        )
    variant_sections = stage_outputs["variants"]
    dimension_to_section = PROMPT_PACKAGE_CONTRACT["prompt_format"]["dimension_to_section"]
    fallback_variants = {
        "camera_motion": "Replace the baseline move with a slow lateral parallax push while preserving subject framing and continuity.",
        "lighting": "Replace the baseline lighting with harder red-black rim light while preserving established white highlights and subject identity.",
        "timing": "Replace the baseline timing with a sharper three-beat progression from establishment through acceleration to a held final graphic while preserving total duration.",
    }
    variants = []
    for dimension in VARIANT_DIMENSIONS:
        prompt = deepcopy(baseline)
        section = dimension_to_section[dimension]
        candidate = canonicalize_prompt_draft(
            {name: deepcopy(variant_sections[dimension] if name == section else baseline[name])
             for name in PROMPT_SECTIONS},
            source_inputs,
            required_sources,
        )[section]
        if candidate == baseline[section]:
            candidate = [_label_atom({"text": fallback_variants[dimension]}, "creative")]
        prompt[section] = candidate
        variants.append({"changed_dimension": dimension, "prompt": prompt})
    draft = {
        **_fixed_package_fields(
            evidence_manifest=evidence_manifest,
            general_vlm=source_inputs["general_vlm"],
            required_sources=required_sources,
            target_engine=target_engine,
            mode=mode,
            generated_at=generated_at,
        ),
        "five_role_review": deepcopy(base["five_role_review"]),
        "prompts": {
            "reconstruction_t2v": deepcopy(baseline),
            "reconstruction_i2v": reconstruction_i2v,
            "enhanced": enhanced,
            "single_variable_variants": variants,
        },
        "anchors": deepcopy(base["anchors"]),
        "negative_constraints": _canonicalize_negative_constraints(
            base["negative_constraints"]
        ),
        "uncertainties": deepcopy(base["uncertainties"]),
    }
    return normalize_fusion_draft(draft)


def _default_http_runner(server_url: str, prompt: str) -> str:
    """Return only the assistant content from a loopback llama-server response."""
    parsed_url = urlparse(server_url)
    if parsed_url.scheme != "http" or parsed_url.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("fusion server must be a local loopback HTTP endpoint")
    endpoint = server_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": "local-model",
        "messages": [
            {
                "role": "system",
                "content": "Return exactly one JSON object that follows the supplied contract. Do not use Markdown fences or commentary.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 16384,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    request = Request(
        endpoint,
        data=dumps_strict_json(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=3600) as response:
            envelope = loads_strict_json(response.read().decode("utf-8", errors="strict"))
        content = envelope["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, UnicodeError, ValueError):
        raise RuntimeError("local llama-server returned an invalid response") from None
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("local llama-server returned empty assistant content")
    return content


def prepare_fusion_dry_run(
    *,
    evidence_manifest: dict,
    skycaptioner: list[dict],
    general_vlm: list[dict],
    asr_ocr: list[dict],
    human_context: list[dict],
    target_engine: dict,
    mode: str,
    generated_at: str,
) -> dict:
    """Build an auditable fusion request without process startup or private runtime paths."""
    source_inputs = {
        "skycaptioner": skycaptioner,
        "general_vlm": general_vlm,
        "asr_ocr": asr_ocr,
        "human_context": human_context,
    }
    reject_sensitive_content(
        {
            "evidence_manifest": evidence_manifest,
            "sources": source_inputs,
            "target_engine": target_engine,
            "metadata": {"mode": mode, "generated_at": generated_at},
        }
    )
    required_sources = build_source_references(source_inputs)
    instruction = build_fusion_instruction(
        evidence_manifest=evidence_manifest,
        skycaptioner=skycaptioner,
        general_vlm=general_vlm,
        asr_ocr=asr_ocr,
        human_context=human_context,
        target_engine=target_engine,
        mode=mode,
        generated_at=generated_at,
    )
    instruction += "\nREQUIRED_SOURCE_REFERENCES_JSON\n"
    instruction += dumps_strict_json(
        required_sources, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    instruction += "\nEND_REQUIRED_SOURCE_REFERENCES_JSON"
    return {
        "mode": "dry-run",
        "required_source_references": required_sources,
        "endpoint_template": "http://127.0.0.1:<port>/v1/chat/completions",
        "instruction": instruction,
    }


def fuse_prompt_package(
    *,
    evidence_manifest: dict,
    skycaptioner: list[dict],
    general_vlm: list[dict],
    asr_ocr: list[dict],
    human_context: list[dict],
    target_engine: dict,
    mode: str,
    generated_at: str,
    server_url: str,
    runner: Runner | None = None,
    raw_output_path: Path | None = None,
) -> dict:
    """Run four bounded local fusion stages and return only a fully validated package."""
    request = prepare_fusion_dry_run(
        evidence_manifest=evidence_manifest,
        skycaptioner=skycaptioner,
        general_vlm=general_vlm,
        asr_ocr=asr_ocr,
        human_context=human_context,
        target_engine=target_engine,
        mode=mode,
        generated_at=generated_at,
    )
    selected_runner = runner or _default_http_runner
    stage_outputs = {}
    raw_outputs = {}
    for stage in FUSION_STAGES:
        baseline = (
            stage_outputs["base"]["reconstruction_t2v"] if "base" in stage_outputs else None
        )
        instruction = build_fusion_stage_instruction(stage, request["instruction"], baseline)
        raw_output = selected_runner(server_url, instruction)
        raw_outputs[stage] = raw_output
        if raw_output_path is not None:
            raw_output_path.parent.mkdir(parents=True, exist_ok=True)
            raw_output_path.write_text(
                dumps_strict_json(raw_outputs, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        stage_outputs[stage] = validate_fusion_stage_output(
            stage, extract_strict_json_object(raw_output)
        )
    package = assemble_staged_fusion(
        stage_outputs=stage_outputs,
        evidence_manifest=evidence_manifest,
        source_inputs={
            "skycaptioner": skycaptioner,
            "general_vlm": general_vlm,
            "asr_ocr": asr_ocr,
            "human_context": human_context,
        },
        required_sources=request["required_source_references"],
        target_engine=target_engine,
        mode=mode,
        generated_at=generated_at,
    )
    validate_prompt_package(
        package,
        evidence_manifest=evidence_manifest,
        required_sources=request["required_source_references"],
        expected_mode=mode,
        expected_generated_at=generated_at,
        target_engine=target_engine,
        source_inputs={
            "skycaptioner": skycaptioner,
            "general_vlm": general_vlm,
            "asr_ocr": asr_ocr,
            "human_context": human_context,
        },
    )
    return package


MARKDOWN_SPECIAL = frozenset("\\`*{}[]<>_#+-.!|()")


def _markdown_escape(value: object) -> str:
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    escaped = []
    for character in text:
        if character == "\n":
            escaped.append("&#10;")
        elif character == "\t":
            escaped.append("&#9;")
        elif ord(character) < 32 or ord(character) == 127:
            escaped.append("�")
        elif character in MARKDOWN_SPECIAL:
            escaped.append("\\" + character)
        else:
            escaped.append(character)
    return "".join(escaped)


def _markdown_code_block(value: str) -> str:
    return "\n".join(f"    {line}" for line in value.splitlines())


def _markdown_list(values: list[str]) -> str:
    return (
        "\n".join(f"- {_markdown_escape(value)}" for value in values)
        if values
        else "- None recorded."
    )


def render_prompt_package(package: dict, template_path: Path | None = None) -> str:
    """Render the shipped Markdown template only after deterministic validation."""
    validate_prompt_package(package)
    template = template_path or Path(__file__).resolve().parents[1] / "assets" / "prompt-package-template.md"
    template_text = template.read_text(encoding="utf-8")

    shot_sections = []
    for shot in package["shots"]:
        evidence = "\n".join(
            f"  - [{_markdown_escape(reference)}](<{quote(reference, safe='/')}>)"
            for reference in shot["evidence_refs"]
        )
        shot_sections.append(
            "\n".join(
                (
                    f"## {_markdown_escape(shot['id'])}",
                    "",
                    f"- Time: {shot['timestamps']['start']} s to {shot['timestamps']['end']} s",
                    f"- Description: {_markdown_escape(shot['description'])}",
                    "- Evidence:",
                    evidence,
                )
            )
        )
    sources = "\n\n".join(
        f"## {_markdown_escape(namespace)}\n\n{_markdown_list(references)}"
        for namespace, references in package["sources"].items()
    )
    role_reviews = "\n".join(
        f"- **{_markdown_escape(role)}:** {_markdown_escape(review)}"
        for role, review in package["five_role_review"].items()
    )
    variants = "\n\n".join(
        f"### {_markdown_escape(variant['changed_dimension'])}\n\n"
        f"{_markdown_code_block(variant['prompt'])}"
        for variant in package["prompts"]["single_variable_variants"]
    )
    values = {
        "mode": _markdown_escape(package["metadata"]["mode"]),
        "generated_at": _markdown_escape(package["metadata"]["generated_at"]),
        **package["media"],
        "shots": "\n\n".join(shot_sections),
        "sources": sources,
        "five_role_review": role_reviews,
        "reconstruction_t2v": _markdown_code_block(package["prompts"]["reconstruction_t2v"]),
        "reconstruction_i2v": _markdown_code_block(package["prompts"]["reconstruction_i2v"]),
        "enhanced": _markdown_code_block(package["prompts"]["enhanced"]),
        "single_variable_variants": variants,
        "engine_name": _markdown_escape(package["engine"]["name"]),
        "engine_parameters": _markdown_code_block(
            dumps_strict_json(
                package["engine"]["parameters"], ensure_ascii=False, indent=2, sort_keys=True
            )
        ),
        "compatibility_notes": _markdown_list(package["engine"]["compatibility_notes"]),
        "anchors": _markdown_list(package["anchors"]),
        "reconstruction_source": _markdown_list(
            package["negative_constraints"]["reconstruction_source"]
        ),
        "generation_stability": _markdown_list(
            package["negative_constraints"]["generation_stability"]
        ),
        "uncertainties": _markdown_list(package["uncertainties"]),
        "attribution_status": _markdown_escape(package["attribution"]["status"]),
        "attribution_entries": _markdown_code_block(
            dumps_strict_json(
                package["attribution"]["entries"],
                ensure_ascii=False,
                indent=2,
            )
        ),
    }
    return template_text.format_map(values)


def write_prompt_package(package: dict, output_dir: Path) -> tuple[Path, Path]:
    """Write JSON and derived Markdown after the complete package passes validation."""
    markdown = render_prompt_package(package)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "prompt-package.json"
    markdown_path = output_dir / "prompt-package.md"
    json_path.write_text(
        dumps_strict_json(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(markdown, encoding="utf-8")
    return json_path, markdown_path


def _load_optional_records(path: Path | None) -> list[dict]:
    return load_records(path) if path is not None else []


def main() -> None:
    parser = argparse.ArgumentParser(description="Fuse evidence into a strict video prompt package.")
    parser.add_argument("evidence_manifest", type=Path)
    parser.add_argument("--skycaptioner", type=Path)
    parser.add_argument("--general-vlm", type=Path)
    parser.add_argument("--asr-ocr", type=Path)
    parser.add_argument("--human-context", type=Path)
    parser.add_argument("--target-engine", type=Path, required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--generated-at")
    parser.add_argument("--server-url")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.task or args.task in {".", ".."} or any(mark in args.task for mark in ("/", "\\")):
        parser.error("--task must be one local task directory name")
    if not args.dry_run and not args.server_url:
        parser.error("--server-url is required unless --dry-run is used")

    evidence_manifest = load_strict_json(args.evidence_manifest)
    target_engine = load_strict_json(args.target_engine)
    generated_at = args.generated_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    inputs = {
        "evidence_manifest": evidence_manifest,
        "skycaptioner": _load_optional_records(args.skycaptioner),
        "general_vlm": _load_optional_records(args.general_vlm),
        "asr_ocr": _load_optional_records(args.asr_ocr),
        "human_context": _load_optional_records(args.human_context),
        "target_engine": target_engine,
        "mode": args.mode,
        "generated_at": generated_at,
    }
    output_dir = Path("D:/VideoLearning/work") / args.task / "video-prompt-reverse"
    if args.dry_run:
        request = prepare_fusion_dry_run(**inputs)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "fusion-dry-run.json"
        output_path.write_text(
            dumps_strict_json(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(output_path)
        return

    package = fuse_prompt_package(
        **inputs,
        server_url=args.server_url,
        raw_output_path=output_dir / "fusion-response.raw.json",
    )
    json_path, markdown_path = write_prompt_package(package, output_dir)
    print(json_path)
    print(markdown_path)


if __name__ == "__main__":
    main()
