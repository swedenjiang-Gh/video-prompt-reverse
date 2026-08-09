"""Deterministic validation for fused prompt packages."""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath


FIVE_ROLES = {
    "screenwriter",
    "director",
    "cinematographer",
    "production_designer",
    "editor",
}
PACKAGE_FIELDS = {
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
}
PROMPT_SECTIONS = ("SUBJECT", "ACTION", "SCENE", "CAMERA", "LIGHTING", "TIMING", "AUDIO", "CONSTRAINTS")
SOURCE_NAMESPACES = {"skycaptioner", "general_vlm", "asr_ocr", "human_context"}
SECRET_KEY = re.compile(
    r"api[_-]?key|token|password|secret|cookie|credential|authorization", re.IGNORECASE
)
SECRET_VALUE = re.compile(
    r"(?:\bBearer\s+\S+|\bsk-[A-Za-z0-9_-]{12,}|\bhf_[A-Za-z0-9]{15,}|"
    r"\b(?:api[_-]?key|token|password|secret|cookie|authorization)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)
PRIVATE_PATH = re.compile(r"(?:\b[A-Za-z]:[\\/]|\\\\[^\\\s]+\\|file://|/(?:home|Users)/)")


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


def _validate_complete_prompt(value: object, location: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location} must be a non-empty string")
    for section in PROMPT_SECTIONS:
        if f"{section}:" not in value:
            raise ValueError(f"{location} is missing {section}")
    if re.search(r"(?m)(?:^|\s)--[a-z][a-z0-9-]*\b", value, re.IGNORECASE):
        raise ValueError(f"{location} contains engine parameter syntax")


def _number(value: object, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{location} must be a number")
    return float(value)


def reject_secret_like_content(value: object) -> None:
    """Reject credential-shaped keys or values without exposing their contents."""
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and SECRET_KEY.search(key):
                raise ValueError("prompt package contains a secret-like key")
            reject_secret_like_content(child)
    elif isinstance(value, list):
        for child in value:
            reject_secret_like_content(child)
    elif isinstance(value, str):
        if SECRET_VALUE.search(value):
            raise ValueError("prompt package contains a secret-like value")


def _scan_private_paths(value: object) -> None:
    if isinstance(value, dict):
        for child in value.values():
            _scan_private_paths(child)
    elif isinstance(value, list):
        for child in value:
            _scan_private_paths(child)
    elif isinstance(value, str):
        if PRIVATE_PATH.search(value):
            raise ValueError("prompt package contains a private path")


def _scan_for_leakage(value: object) -> None:
    reject_secret_like_content(value)
    _scan_private_paths(value)


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
    metadata = _require_exact_keys(package["metadata"], {"mode", "generated_at"}, "metadata")
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
        {"reconstruction_source", "generation_stability"},
        "negative_constraints",
    )
    for category, values in negatives.items():
        if not isinstance(values, list) or not values or any(
            not isinstance(value, str) or not value.strip() for value in values
        ):
            raise ValueError(
                f"negative_constraints.{category} must be a non-empty list of strings"
            )
    media = _require_exact_keys(
        package["media"], {"duration_seconds", "width", "height", "fps"}, "media"
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
            shot, {"id", "timestamps", "evidence_refs", "description"}, f"shot {index}"
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
        if any(
            "\\" in reference
            or PurePosixPath(reference).is_absolute()
            or ".." in PurePosixPath(reference).parts
            for reference in references
        ):
            raise ValueError(f"shot {index}.evidence_refs must use portable relative paths")
        timestamps = _require_exact_keys(shot["timestamps"], {"start", "end"}, f"shot {index}.timestamps")
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
        package["engine"], {"name", "parameters", "compatibility_notes"}, "engine"
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
        {"reconstruction_t2v", "reconstruction_i2v", "enhanced", "single_variable_variants"},
        "prompts",
    )
    for name in ("reconstruction_t2v", "reconstruction_i2v", "enhanced"):
        _validate_complete_prompt(prompts[name], name)
    variants = prompts["single_variable_variants"]
    if not isinstance(variants, list) or len(variants) != 3:
        raise ValueError("prompts.single_variable_variants requires exactly three variants")
    dimensions = []
    for index, variant in enumerate(variants):
        variant = _require_exact_keys(variant, {"changed_dimension", "prompt"}, f"variant {index}")
        dimension = variant["changed_dimension"]
        if not isinstance(dimension, str) or not dimension.strip():
            raise ValueError(f"variant {index}.changed_dimension must be a non-empty string")
        _validate_complete_prompt(variant["prompt"], f"variant {index} prompt")
        dimensions.append(dimension)
    if len(set(dimensions)) != 3:
        raise ValueError("variants require a unique changed_dimension")


def _load_optional_json(path: Path | None) -> object | None:
    return json.loads(path.read_text(encoding="utf-8")) if path is not None else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate one strict video prompt package.")
    parser.add_argument("prompt_package", type=Path)
    parser.add_argument("--evidence-manifest", type=Path)
    parser.add_argument("--required-sources", type=Path)
    parser.add_argument("--target-engine", type=Path)
    parser.add_argument("--mode")
    parser.add_argument("--generated-at")
    args = parser.parse_args()

    package = json.loads(args.prompt_package.read_text(encoding="utf-8"))
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
