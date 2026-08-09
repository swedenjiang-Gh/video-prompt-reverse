"""Deterministic validation for fused prompt packages."""

import argparse
import json
import math
import re
import unicodedata
from datetime import datetime
from pathlib import Path


PROMPT_PACKAGE_CONTRACT = {
    "objects": {
        "prompt_package": [
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
        "shot": ["id", "timestamps", "evidence_refs", "description"],
        "timestamps": ["start", "end"],
        "sources": ["skycaptioner", "general_vlm", "asr_ocr", "human_context"],
        "five_role_review": [
            "screenwriter",
            "director",
            "cinematographer",
            "production_designer",
            "editor",
        ],
        "prompts": [
            "reconstruction_t2v",
            "reconstruction_i2v",
            "enhanced",
            "single_variable_variants",
        ],
        "single_variable_variant": ["changed_dimension", "prompt"],
        "engine": ["name", "parameters", "compatibility_notes"],
        "negative_constraints": ["reconstruction_source", "generation_stability"],
    },
    "types": {
        "metadata.mode": "non-empty string",
        "metadata.generated_at": "timezone-aware ISO 8601 string",
        "media.duration_seconds": "positive finite number",
        "media.width": "positive integer",
        "media.height": "positive integer",
        "media.fps": "positive finite number",
        "shots": "non-empty array of shot objects",
        "shot.id": "unique non-empty string",
        "shot.timestamps.start": "non-negative finite number",
        "shot.timestamps.end": "positive finite number",
        "shot.evidence_refs": "non-empty array of portable relative path strings",
        "shot.description": "non-empty string",
        "sources.*": "array of own-namespace reference strings",
        "five_role_review.*": "non-empty string",
        "prompts.reconstruction_t2v": "complete standalone prompt string",
        "prompts.reconstruction_i2v": "complete standalone prompt string",
        "prompts.enhanced": "complete standalone prompt string",
        "prompts.single_variable_variants": "array of exactly 3 variant objects",
        "single_variable_variant.changed_dimension": "unique allowed dimension string",
        "single_variable_variant.prompt": "complete standalone prompt string",
        "engine.name": "non-empty string",
        "engine.parameters": "non-empty object of named finite scalar values",
        "engine.compatibility_notes": "array of non-empty strings",
        "anchors": "non-empty array of non-empty strings",
        "negative_constraints.*": "non-empty array of non-empty strings",
        "uncertainties": "array of non-empty strings",
    },
    "prompt_format": {
        "ordered_sections": [
            "SUBJECT",
            "ACTION",
            "SCENE",
            "CAMERA",
            "LIGHTING",
            "TIMING",
            "AUDIO",
            "CONSTRAINTS",
        ],
        "dimension_to_section": {
            "subject": "SUBJECT",
            "action": "ACTION",
            "scene": "SCENE",
            "camera": "CAMERA",
            "camera_motion": "CAMERA",
            "lighting": "LIGHTING",
            "timing": "TIMING",
            "audio": "AUDIO",
            "constraints": "CONSTRAINTS",
        },
        "variant_baseline": "prompts.reconstruction_t2v",
        "variant_count": 3,
    },
    "strict_json": (
        "one bare RFC 8259 object; no duplicate keys, non-finite numbers, prefix, suffix, or fences"
    ),
    "invariants": [
        "all listed objects reject additional fields",
        "metadata exactly matches the requested mode and generation time",
        "media exactly matches the evidence manifest",
        "shots preserve manifest order, timestamps, and evidence references",
        "shot timestamps are chronological, non-overlapping, and within media bounds",
        "sources exactly match required own-namespace references",
        "each variant changes exactly its declared section from reconstruction_t2v",
        "engine name and parameters match the target engine",
        "engine parameters are structured scalars and absent from prompt prose",
        "negative categories are non-empty and normalized-disjoint",
        "credentials and private roots are forbidden before and after fusion",
        "evidence references are portable local relative paths",
        "Markdown is rendered from validated data only",
    ],
}

PACKAGE_FIELDS = set(PROMPT_PACKAGE_CONTRACT["objects"]["prompt_package"])
FIVE_ROLES = set(PROMPT_PACKAGE_CONTRACT["objects"]["five_role_review"])
PROMPT_SECTIONS = tuple(PROMPT_PACKAGE_CONTRACT["prompt_format"]["ordered_sections"])
PROMPT_DIMENSION_SECTIONS = PROMPT_PACKAGE_CONTRACT["prompt_format"]["dimension_to_section"]
SOURCE_NAMESPACES = set(PROMPT_PACKAGE_CONTRACT["objects"]["sources"])
SECRET_VALUE = re.compile(
    r"(?:\bBearer\s+\S+|\bsk-[A-Za-z0-9_-]{12,}|\bhf_[A-Za-z0-9]{15,}|"
    r"\bgithub_pat_[A-Za-z0-9_]{20,}|"
    r"\b(?:api[_-]?key|token|password|secret|cookie|authorization)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)
PRIVATE_PATH = re.compile(r"(?:\b[A-Za-z]:[\\/]|\\\\[^\\\s]+\\|file://|/(?:home|Users)/)")


def loads_strict_json(raw: str) -> object:
    """Parse one standards-compliant JSON value without duplicate object keys."""
    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = value
        return result

    def reject_non_finite_number(value: str) -> None:
        raise ValueError(f"non-finite JSON number: {value}")

    def reject_non_finite_floats(value: object) -> None:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("non-finite JSON number")
        if isinstance(value, dict):
            for child in value.values():
                reject_non_finite_floats(child)
        elif isinstance(value, list):
            for child in value:
                reject_non_finite_floats(child)

    try:
        parsed = json.loads(
            raw,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_non_finite_number,
        )
        reject_non_finite_floats(parsed)
        return parsed
    except (TypeError, ValueError):
        raise ValueError("input must contain exactly one strict JSON value") from None


def load_strict_json(path: Path) -> object:
    return loads_strict_json(path.read_text(encoding="utf-8"))


def dumps_strict_json(value: object, **kwargs: object) -> str:
    try:
        return json.dumps(value, allow_nan=False, **kwargs)
    except (TypeError, ValueError):
        raise ValueError("value cannot be represented as strict JSON") from None


def _require_exact_keys(value: object, expected: set[str], location: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")
    missing = expected - set(value)
    extra = set(value) - expected
    if missing:
        raise ValueError(f"{location} has missing fields: {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"{location} has extra fields: {', '.join(sorted(extra))}")
    return value


def _validate_complete_prompt(value: object, location: str) -> dict[str, str]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location} must be a non-empty string")
    if re.search(r"(?m)(?:^|\s)--[a-z][a-z0-9-]*\b", value, re.IGNORECASE):
        raise ValueError(f"{location} contains engine parameter syntax")
    parsed = []
    for line in value.splitlines():
        match = re.fullmatch(r"([A-Z][A-Z0-9_ ]*):[ \t]*(.*)", line)
        if match is None:
            parsed.append(("", ""))
        else:
            parsed.append((match.group(1), match.group(2).strip()))
    if (
        [section for section, _ in parsed] != list(PROMPT_SECTIONS)
        or any(not section_value for _, section_value in parsed)
    ):
        expected = ", ".join(PROMPT_SECTIONS)
        raise ValueError(f"{location} sections must be exactly ordered and non-empty: {expected}")
    return dict(parsed)


def _number(value: object, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{location} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{location} must be finite")
    return number


def _is_portable_evidence_reference(reference: str) -> bool:
    if (
        "\\" in reference
        or ":" in reference
        or reference.startswith("/")
        or reference.startswith("./")
        or reference.endswith("/")
        or "//" in reference
        or re.search(r"[<>\"|?*]", reference)
        or any(ord(character) < 32 or ord(character) == 127 for character in reference)
    ):
        return False
    parts = reference.split("/")
    for part in parts:
        if part in {"", ".", ".."} or part.endswith((".", " ")):
            return False
        basename = part.split(".", 1)[0].casefold()
        if basename in {"con", "prn", "aux", "nul"} or re.fullmatch(
            r"(?:com|lpt)[1-9]", basename
        ):
            return False
    return True


def _normalize_constraint(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\W_]+", " ", normalized).strip()


def _is_secret_key(key: str) -> bool:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    parts = [part for part in re.split(r"[^a-z0-9]+", normalized.lower()) if part]
    if not parts:
        return False
    if "".join(parts) in {
        "apikey",
        "accesstoken",
        "authtoken",
        "bearertoken",
        "privatekey",
        "clientsecret",
    }:
        return True
    if any(
        part in {"password", "passwd", "secret", "cookie", "credential", "authorization"}
        for part in parts
    ):
        return True
    if parts[-1] == "token":
        return True
    pairs = set(zip(parts, parts[1:]))
    return ("api", "key") in pairs or ("private", "key") in pairs


def reject_sensitive_content(value: object) -> None:
    """Reject credential-shaped content and private roots without exposing values."""
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and _is_secret_key(key):
                raise ValueError("prompt package contains a secret-like key")
            reject_sensitive_content(child)
    elif isinstance(value, list):
        for child in value:
            reject_sensitive_content(child)
    elif isinstance(value, str):
        if SECRET_VALUE.search(value):
            raise ValueError("prompt package contains a secret-like value")
        if PRIVATE_PATH.search(value):
            raise ValueError("prompt package contains a private path")


def _scan_for_leakage(value: object) -> None:
    reject_sensitive_content(value)


def validate_prompt_package(
    package: dict,
    *,
    evidence_manifest: dict | None = None,
    required_sources: dict | None = None,
    expected_mode: str | None = None,
    expected_generated_at: str | None = None,
    target_engine: dict | None = None,
) -> None:
    """Reject prompt packages that violate the strict output contract."""
    _scan_for_leakage(package)
    package = _require_exact_keys(package, PACKAGE_FIELDS, "prompt package")
    metadata = _require_exact_keys(
        package["metadata"], set(PROMPT_PACKAGE_CONTRACT["objects"]["metadata"]), "metadata"
    )
    if not isinstance(metadata["mode"], str) or not metadata["mode"].strip():
        raise ValueError("metadata.mode must be a non-empty string")
    if not isinstance(metadata["generated_at"], str):
        raise ValueError("metadata.generated_at must be a string with timezone")
    try:
        generated_at = datetime.fromisoformat(metadata["generated_at"].replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("metadata.generated_at must be an ISO timestamp with timezone") from None
    if generated_at.tzinfo is None:
        raise ValueError("metadata.generated_at must include a timezone")
    if expected_mode is not None and metadata["mode"] != expected_mode:
        raise ValueError("package does not preserve requested metadata")
    if expected_generated_at is not None and metadata["generated_at"] != expected_generated_at:
        raise ValueError("package does not preserve requested metadata")
    negatives = _require_exact_keys(
        package["negative_constraints"],
        set(PROMPT_PACKAGE_CONTRACT["objects"]["negative_constraints"]),
        "negative_constraints",
    )
    for category, values in negatives.items():
        if not isinstance(values, list) or not values or any(
            not isinstance(value, str) or not value.strip() for value in values
        ):
            raise ValueError(
                f"negative_constraints.{category} must be a non-empty list of strings"
            )
    reconstruction_negatives = {
        _normalize_constraint(value) for value in negatives["reconstruction_source"]
    }
    stability_negatives = {
        _normalize_constraint(value) for value in negatives["generation_stability"]
    }
    if reconstruction_negatives & stability_negatives:
        raise ValueError("negative constraint categories must not overlap")
    media = _require_exact_keys(
        package["media"], set(PROMPT_PACKAGE_CONTRACT["objects"]["media"]), "media"
    )
    duration = _number(media["duration_seconds"], "media.duration_seconds")
    fps = _number(media["fps"], "media.fps")
    if duration <= 0 or fps <= 0:
        raise ValueError("media duration_seconds and fps must be positive")
    for dimension in ("width", "height"):
        value = media[dimension]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"media.{dimension} must be a positive integer")
    anchors = package["anchors"]
    if not isinstance(anchors, list) or not anchors or any(
        not isinstance(anchor, str) or not anchor.strip() for anchor in anchors
    ):
        raise ValueError("anchors must be a non-empty list of strings")
    uncertainties = package["uncertainties"]
    if not isinstance(uncertainties, list) or any(
        not isinstance(item, str) or not item.strip() for item in uncertainties
    ):
        raise ValueError("uncertainties must be a list of non-empty strings")
    shots = package["shots"]
    if not isinstance(shots, list) or not shots:
        raise ValueError("shots must be a non-empty list")
    previous_start = -1.0
    previous_end = 0.0
    shot_ids = set()
    for index, shot in enumerate(shots):
        shot = _require_exact_keys(
            shot, set(PROMPT_PACKAGE_CONTRACT["objects"]["shot"]), f"shot {index}"
        )
        if not isinstance(shot["id"], str) or not shot["id"].strip() or shot["id"] in shot_ids:
            raise ValueError("shot ids must be unique non-empty strings")
        shot_ids.add(shot["id"])
        if not isinstance(shot["description"], str) or not shot["description"].strip():
            raise ValueError(f"shot {index}.description must be a non-empty string")
        references = shot["evidence_refs"]
        if not isinstance(references, list) or not references or any(
            not isinstance(reference, str) or not reference.strip() for reference in references
        ):
            raise ValueError(f"shot {index}.evidence_refs must be a non-empty list of strings")
        if any(not _is_portable_evidence_reference(reference) for reference in references):
            raise ValueError(f"shot {index}.evidence_refs must use portable relative paths")
        timestamps = _require_exact_keys(
            shot["timestamps"],
            set(PROMPT_PACKAGE_CONTRACT["objects"]["timestamps"]),
            f"shot {index}.timestamps",
        )
        start = _number(timestamps["start"], f"shot {index}.timestamps.start")
        end = _number(timestamps["end"], f"shot {index}.timestamps.end")
        if start < previous_start:
            raise ValueError("shots must be chronological")
        if index and start < previous_end:
            raise ValueError("shots must not overlap")
        if start < 0 or start >= end or end > duration:
            raise ValueError("shot timestamps must be within media bounds")
        previous_start = start
        previous_end = end
    sources = _require_exact_keys(package["sources"], SOURCE_NAMESPACES, "sources")
    for namespace, references in sources.items():
        if not isinstance(references, list) or any(
            not isinstance(reference, str) or not reference.strip() for reference in references
        ):
            raise ValueError(f"sources.{namespace} must be a list of non-empty references")
        if any(not reference.startswith(f"{namespace}:") for reference in references):
            raise ValueError(f"sources.{namespace} contains a cross-namespace reference")
    if required_sources is not None and sources != required_sources:
        raise ValueError("source provenance does not match fusion inputs")
    if evidence_manifest is not None:
        manifest_media = evidence_manifest.get("media", {})
        expected_media = {
            name: manifest_media.get(name) for name in ("duration_seconds", "width", "height", "fps")
        }
        if media != expected_media:
            raise ValueError("package does not preserve manifest media facts")
        manifest_shots = evidence_manifest.get("shots")
        if not isinstance(manifest_shots, list) or [shot["id"] for shot in shots] != [
            shot["id"] for shot in manifest_shots
        ]:
            raise ValueError("package does not preserve manifest shot order")
        for shot, manifest_shot in zip(shots, manifest_shots, strict=True):
            if shot["timestamps"] != manifest_shot.get("timestamps"):
                raise ValueError("package does not preserve manifest shot timestamps")
            expected_references = [item["path"] for item in manifest_shot.get("evidence", [])]
            if shot["evidence_refs"] != expected_references:
                raise ValueError("package evidence provenance does not match the manifest")
    engine = _require_exact_keys(
        package["engine"], set(PROMPT_PACKAGE_CONTRACT["objects"]["engine"]), "engine"
    )
    if not isinstance(engine["name"], str) or not engine["name"].strip():
        raise ValueError("engine.name must be a non-empty string")
    parameters = engine["parameters"]
    if not isinstance(parameters, dict):
        raise ValueError("engine.parameters must be an object")
    if not parameters:
        raise ValueError("engine.parameters must be non-empty")
    if any(
        not isinstance(name, str)
        or not name.strip()
        or isinstance(value, (dict, list))
        or value is None
        for name, value in parameters.items()
    ):
        raise ValueError("engine.parameters must contain named scalar values")
    if any(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and not math.isfinite(value)
        for value in parameters.values()
    ):
        raise ValueError("engine.parameters must contain finite scalar values")
    notes = engine["compatibility_notes"]
    if not isinstance(notes, list) or any(
        not isinstance(note, str) or not note.strip() for note in notes
    ):
        raise ValueError("engine.compatibility_notes must be a list of non-empty strings")
    if target_engine is not None:
        if not isinstance(target_engine, dict) or any(
            target_engine.get(field) != engine[field] for field in ("name", "parameters")
        ):
            raise ValueError("package does not preserve the target engine")
        if (
            "compatibility_notes" in target_engine
            and target_engine["compatibility_notes"] != engine["compatibility_notes"]
        ):
            raise ValueError("package does not preserve the target engine")
    roles = _require_exact_keys(package["five_role_review"], FIVE_ROLES, "five_role_review")
    for role, review in roles.items():
        if not isinstance(review, str) or not review.strip():
            raise ValueError(f"five_role_review.{role} must be a non-empty string")

    prompts = _require_exact_keys(
        package["prompts"],
        set(PROMPT_PACKAGE_CONTRACT["objects"]["prompts"]),
        "prompts",
    )
    baseline_sections = _validate_complete_prompt(
        prompts["reconstruction_t2v"], "reconstruction_t2v"
    )
    for name in ("reconstruction_i2v", "enhanced"):
        _validate_complete_prompt(prompts[name], name)
    variants = prompts["single_variable_variants"]
    variant_count = PROMPT_PACKAGE_CONTRACT["prompt_format"]["variant_count"]
    if not isinstance(variants, list) or len(variants) != variant_count:
        raise ValueError("prompts.single_variable_variants requires exactly three variants")
    dimensions = []
    for index, variant in enumerate(variants):
        variant = _require_exact_keys(
            variant,
            set(PROMPT_PACKAGE_CONTRACT["objects"]["single_variable_variant"]),
            f"variant {index}",
        )
        dimension = variant["changed_dimension"]
        if not isinstance(dimension, str) or not dimension.strip():
            raise ValueError(f"variant {index}.changed_dimension must be a non-empty string")
        if dimension not in PROMPT_DIMENSION_SECTIONS:
            raise ValueError("variant requires an allowed changed_dimension")
        if dimension in dimensions:
            raise ValueError("variants require a unique changed_dimension")
        dimensions.append(dimension)
        variant_sections = _validate_complete_prompt(variant["prompt"], f"variant {index} prompt")
        differences = [
            section
            for section in PROMPT_SECTIONS
            if variant_sections[section] != baseline_sections[section]
        ]
        declared_section = PROMPT_DIMENSION_SECTIONS[dimension]
        if differences != [declared_section]:
            raise ValueError(
                f"variant {dimension} must change only {declared_section} from reconstruction_t2v"
            )


def _load_optional_json(path: Path | None) -> object | None:
    return load_strict_json(path) if path is not None else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate one strict video prompt package.")
    parser.add_argument("prompt_package", type=Path)
    parser.add_argument("--evidence-manifest", type=Path)
    parser.add_argument("--required-sources", type=Path)
    parser.add_argument("--target-engine", type=Path)
    parser.add_argument("--mode")
    parser.add_argument("--generated-at")
    args = parser.parse_args()

    package = load_strict_json(args.prompt_package)
    validate_prompt_package(
        package,
        evidence_manifest=_load_optional_json(args.evidence_manifest),
        required_sources=_load_optional_json(args.required_sources),
        expected_mode=args.mode,
        expected_generated_at=args.generated_at,
        target_engine=_load_optional_json(args.target_engine),
    )
    print("valid")


if __name__ == "__main__":
    main()
