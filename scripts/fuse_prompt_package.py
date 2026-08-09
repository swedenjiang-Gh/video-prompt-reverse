"""Fuse separated observations into a strict prompt package."""

import argparse
import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

try:
    from scripts.validate_prompt_package import reject_secret_like_content, validate_prompt_package
except ModuleNotFoundError:  # Direct script execution.
    from validate_prompt_package import reject_secret_like_content, validate_prompt_package

SOURCE_NAMESPACES = ("skycaptioner", "general_vlm", "asr_ocr", "human_context")
Runner = Callable[[list[str], str], str]
OUTPUT_CONTRACT = {
    "top_level_fields": [
        "metadata",
        "media",
        "shots",
        "sources",
        "five_role_review",
        "prompts",
        "engine",
        "anchors",
        "negative_constraints",
        "uncertainties",
    ],
    "metadata": ["mode", "generated_at"],
    "media": ["duration_seconds", "width", "height", "fps"],
    "shot_fields": ["id", "timestamps", "evidence_refs", "description"],
    "sources": list(SOURCE_NAMESPACES),
    "five_role_review": [
        "screenwriter",
        "director",
        "cinematographer",
        "production_designer",
        "editor",
    ],
    "prompts": {
        "required": ["reconstruction_t2v", "reconstruction_i2v", "enhanced"],
        "single_variable_variant_count": 3,
        "variant_fields": ["changed_dimension", "prompt"],
        "standalone_sections": [
            "SUBJECT",
            "ACTION",
            "SCENE",
            "CAMERA",
            "LIGHTING",
            "TIMING",
            "AUDIO",
            "CONSTRAINTS",
        ],
    },
    "engine": ["name", "parameters", "compatibility_notes"],
    "negative_constraints": ["reconstruction_source", "generation_stability"],
    "strict_json": "one bare object with no prefix, suffix, or fences",
}


def load_records(path: Path) -> list[dict]:
    """Load a JSON object/array or JSONL records from a local observation file."""
    raw = path.read_text(encoding="utf-8")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        try:
            parsed = [json.loads(line) for line in raw.splitlines() if line.strip()]
        except json.JSONDecodeError:
            raise ValueError("observation input must be JSON or JSONL") from None
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
            "Produce one prompt-package JSON object.",
            "Do not merge source namespaces. Copy only the required provenance references into sources.",
            "Do not emit credentials, private machine roots, model paths, or parameter flags in prompt prose.",
            "PACKAGE_METADATA_JSON",
            json.dumps(
                {"mode": mode, "generated_at": generated_at},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "END_PACKAGE_METADATA_JSON",
            "OUTPUT_CONTRACT_JSON",
            json.dumps(OUTPUT_CONTRACT, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "END_OUTPUT_CONTRACT_JSON",
            "EVIDENCE_MANIFEST_JSON",
            json.dumps(evidence_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "END_EVIDENCE_MANIFEST_JSON",
            "SOURCE_INPUTS_JSON",
            json.dumps(sources, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "END_SOURCE_INPUTS_JSON",
            "TARGET_ENGINE_JSON",
            json.dumps(target_engine, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "END_TARGET_ENGINE_JSON",
        )
    )


def extract_strict_json_object(raw_output: str) -> dict:
    """Accept only one bare JSON object, with no model commentary or fences."""
    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = value
        return result

    def reject_non_finite_number(value: str) -> None:
        raise ValueError(f"non-finite JSON number: {value}")

    try:
        package = json.loads(
            raw_output,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_non_finite_number,
        )
    except (TypeError, ValueError):
        raise ValueError("model output must contain exactly one JSON object") from None
    if not isinstance(package, dict):
        raise ValueError("model output must contain exactly one JSON object")
    return package


def build_llama_arguments(llama_executable: str, model_path: str) -> list[str]:
    """Return a structured llama.cpp argument vector; the prompt is sent on stdin."""
    return [
        llama_executable,
        "-m",
        model_path,
        "--ctx-size",
        "32768",
        "--temp",
        "0",
        "--no-display-prompt",
    ]


def _default_runner(arguments: list[str], prompt: str) -> str:
    """Run only verified local files and keep prompt/runtime values out of logs."""
    executable = Path(arguments[0])
    model = Path(arguments[2])
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError("llama executable must be an existing local file")
    if not model.is_absolute() or not model.is_file():
        raise ValueError("llama model must be an existing local file")
    completed = subprocess.run(
        arguments,
        input=prompt,
        capture_output=True,
        text=True,
        shell=False,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("local llama.cpp fusion failed")
    return completed.stdout


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
    reject_secret_like_content(
        {
            "evidence_manifest": evidence_manifest,
            "sources": source_inputs,
            "target_engine": target_engine,
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
    instruction += json.dumps(required_sources, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    instruction += "\nEND_REQUIRED_SOURCE_REFERENCES_JSON"
    return {
        "mode": "dry-run",
        "required_source_references": required_sources,
        "argument_template": build_llama_arguments("<llama-executable>", "<local-model>"),
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
    llama_executable: str,
    model_path: str,
    runner: Runner | None = None,
) -> dict:
    """Run one local fusion request and return only a fully validated package."""
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
    arguments = build_llama_arguments(llama_executable, model_path)
    raw_output = (runner or _default_runner)(arguments, request["instruction"])
    package = extract_strict_json_object(raw_output)
    validate_prompt_package(
        package,
        evidence_manifest=evidence_manifest,
        required_sources=request["required_source_references"],
        expected_mode=mode,
        expected_generated_at=generated_at,
        target_engine=target_engine,
    )
    return package


def _markdown_list(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- None recorded."


def render_prompt_package(package: dict, template_path: Path | None = None) -> str:
    """Render the shipped Markdown template only after deterministic validation."""
    validate_prompt_package(package)
    template = template_path or Path(__file__).resolve().parents[1] / "assets" / "prompt-package-template.md"
    template_text = template.read_text(encoding="utf-8")

    shot_sections = []
    for shot in package["shots"]:
        evidence = "\n".join(
            f"  - [{reference}](<{reference}>)" for reference in shot["evidence_refs"]
        )
        shot_sections.append(
            "\n".join(
                (
                    f"## {shot['id']}",
                    "",
                    f"- Time: {shot['timestamps']['start']} s to {shot['timestamps']['end']} s",
                    f"- Description: {shot['description']}",
                    "- Evidence:",
                    evidence,
                )
            )
        )
    sources = "\n\n".join(
        f"## {namespace}\n\n{_markdown_list(references)}"
        for namespace, references in package["sources"].items()
    )
    role_reviews = _markdown_list(
        [f"**{role}:** {review}" for role, review in package["five_role_review"].items()]
    )
    variants = "\n\n".join(
        f"### {variant['changed_dimension']}\n\n{variant['prompt']}"
        for variant in package["prompts"]["single_variable_variants"]
    )
    values = {
        "mode": package["metadata"]["mode"],
        "generated_at": package["metadata"]["generated_at"],
        **package["media"],
        "shots": "\n\n".join(shot_sections),
        "sources": sources,
        "five_role_review": role_reviews,
        "reconstruction_t2v": package["prompts"]["reconstruction_t2v"],
        "reconstruction_i2v": package["prompts"]["reconstruction_i2v"],
        "enhanced": package["prompts"]["enhanced"],
        "single_variable_variants": variants,
        "engine_name": package["engine"]["name"],
        "engine_parameters": json.dumps(
            package["engine"]["parameters"], ensure_ascii=False, indent=2, sort_keys=True
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
    }
    return template_text.format_map(values)


def write_prompt_package(package: dict, output_dir: Path) -> tuple[Path, Path]:
    """Write JSON and derived Markdown after the complete package passes validation."""
    markdown = render_prompt_package(package)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "prompt-package.json"
    markdown_path = output_dir / "prompt-package.md"
    json_path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
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
    parser.add_argument("--llama-executable")
    parser.add_argument("--model-path")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.task or args.task in {".", ".."} or any(mark in args.task for mark in ("/", "\\")):
        parser.error("--task must be one local task directory name")
    if not args.dry_run and (not args.llama_executable or not args.model_path):
        parser.error("--llama-executable and --model-path are required unless --dry-run is used")

    evidence_manifest = json.loads(args.evidence_manifest.read_text(encoding="utf-8"))
    target_engine = json.loads(args.target_engine.read_text(encoding="utf-8"))
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
            json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(output_path)
        return

    package = fuse_prompt_package(
        **inputs,
        llama_executable=args.llama_executable,
        model_path=args.model_path,
    )
    json_path, markdown_path = write_prompt_package(package, output_dir)
    print(json_path)
    print(markdown_path)


if __name__ == "__main__":
    main()
