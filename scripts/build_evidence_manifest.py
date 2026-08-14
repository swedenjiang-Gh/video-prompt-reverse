"""Assemble structured video evidence from video-learning artifacts."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    from scripts.output_paths import resolve_task_output
except ModuleNotFoundError:
    from output_paths import resolve_task_output


def build_manifest(video_path: Path, probe: dict, intervals: list[dict], frames: list[dict]) -> dict:
    """Return a chronological evidence manifest without rescanning the source video."""
    duration = probe["duration_seconds"]
    if duration <= 0:
        raise ValueError("duration_seconds must be positive")

    shot_ids = set()
    shots = []
    for interval in sorted(intervals, key=lambda item: item["start"]):
        start = interval["start"]
        end = interval["end"]
        shot_id = interval["id"]
        if shot_id in shot_ids:
            raise ValueError("shot ids must be unique")
        if start < 0 or end > duration or start >= end:
            raise ValueError("shot timestamps must be within media bounds")
        shot_ids.add(shot_id)

        evidence = [
            {
                "role": role,
                "timestamp": frame["timestamp"],
                "path": frame["path"],
            }
            for role in ("entry", "peak", "exit")
            for frame in frames
            if frame["shot_id"] == shot_id and frame["role"] == role
        ]
        if len(evidence) != 3:
            raise ValueError("each shot requires entry, peak, and exit evidence")
        if any(frame["timestamp"] < start or frame["timestamp"] > end for frame in evidence):
            raise ValueError("evidence timestamp is outside shot bounds")
        shots.append(
            {
                "id": shot_id,
                "timestamps": {"start": start, "end": end},
                "evidence": evidence,
            }
        )

    manifest = {
        "media": {
            "video_path": video_path.as_posix(),
            "duration_seconds": probe["duration_seconds"],
            "width": probe["width"],
            "height": probe["height"],
            "fps": probe["fps"],
        },
        "shots": shots,
        "source_attribution": {
            "intervals": "event-scan",
            "frames": "extracted-frames",
        },
    }
    validate_manifest(manifest)
    return manifest


def normalize_event_intervals(intervals: list[dict], duration: float) -> list[dict]:
    """Clamp delegated event intervals so extraction uses media-bounded times."""
    normalized = []
    for interval in intervals:
        start = max(0.0, interval["start"])
        end = min(interval["end"], duration)
        if start >= end:
            continue
        normalized.append(
            {
                **interval,
                "start": start,
                "peak": min(max(interval["peak"], start), end),
                "end": end,
            }
        )
    return normalized


def _validate_schema(instance: object, schema: dict) -> None:
    """Validate the small JSON Schema subset used by the public manifest schema."""
    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(instance, dict):
            raise ValueError("analysis schema requires an object")
        properties = schema.get("properties", {})
        missing = [key for key in schema.get("required", []) if key not in instance]
        if missing:
            raise ValueError("analysis schema has missing required properties")
        if schema.get("additionalProperties") is False and set(instance) - set(properties):
            raise ValueError("analysis schema forbids additional properties")
        for key, value in instance.items():
            if key in properties:
                _validate_schema(value, properties[key])
    elif expected_type == "array":
        if not isinstance(instance, list):
            raise ValueError("analysis schema requires an array")
        if len(instance) < schema.get("minItems", 0) or len(instance) > schema.get("maxItems", float("inf")):
            raise ValueError("analysis schema has an invalid array length")
        for item in instance:
            _validate_schema(item, schema["items"])
    elif expected_type == "string":
        if not isinstance(instance, str) or len(instance) < schema.get("minLength", 0):
            raise ValueError("analysis schema requires a non-empty string")
    elif expected_type == "number":
        if isinstance(instance, bool) or not isinstance(instance, (int, float)):
            raise ValueError("analysis schema requires a number")
        if instance < schema.get("minimum", float("-inf")):
            raise ValueError("analysis schema number is below minimum")
    elif expected_type == "integer":
        if isinstance(instance, bool) or not isinstance(instance, int):
            raise ValueError("analysis schema requires an integer")
        if instance < schema.get("minimum", float("-inf")):
            raise ValueError("analysis schema integer is below minimum")

    if "enum" in schema and instance not in schema["enum"]:
        raise ValueError("analysis schema value is not allowed")


def validate_manifest(manifest: dict) -> None:
    """Validate a manifest against the shipped public schema and cross-field rules."""
    schema_path = Path(__file__).resolve().parents[1] / "assets" / "analysis-schema.json"
    _validate_schema(manifest, json.loads(schema_path.read_text(encoding="utf-8")))
    previous_start = -1.0
    duration = manifest["media"]["duration_seconds"]
    for shot in manifest["shots"]:
        start = shot["timestamps"]["start"]
        end = shot["timestamps"]["end"]
        if start < previous_start or start >= end or end > duration:
            raise ValueError("analysis schema has invalid shot bounds")
        if [frame["role"] for frame in shot["evidence"]] != ["entry", "peak", "exit"]:
            raise ValueError("analysis schema requires entry, peak, and exit evidence")
        if any(frame["timestamp"] < start or frame["timestamp"] > end for frame in shot["evidence"]):
            raise ValueError("analysis schema evidence is outside shot bounds")
        previous_start = start


def run_evidence_extraction(
    video_path: Path,
    probe: dict,
    output_dir: Path,
    video_learning_scripts: Path,
) -> tuple[dict, list[dict]]:
    """Scan, bound event intervals, then extract frames from those bounded intervals."""
    event_manifest_path = output_dir / "event-manifest.json"
    frame_dir = output_dir / "evidence-frames"
    subprocess.run(
        [sys.executable, str(video_learning_scripts / "scan_events.py"), str(video_path), "--output", str(event_manifest_path)],
        check=True,
    )
    event_manifest = json.loads(event_manifest_path.read_text(encoding="utf-8"))
    event_manifest["intervals"] = normalize_event_intervals(
        event_manifest["intervals"],
        probe["duration_seconds"],
    )
    event_manifest_path.write_text(
        json.dumps(event_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    extracted = subprocess.run(
        [sys.executable, str(video_learning_scripts / "extract_event_frames.py"), str(video_path), str(event_manifest_path), str(frame_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    return event_manifest, json.loads(extracted.stdout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a video-prompt-reverse evidence manifest.")
    parser.add_argument("video_path", type=Path)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--project-output", type=Path)
    args = parser.parse_args()

    output_dir = resolve_task_output(
        args.task,
        output_root=args.output_root,
        project_output=args.project_output,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    video_learning_scripts = Path(__file__).resolve().parents[2] / "video-learning" / "scripts"
    probe = json.loads(args.probe.read_text(encoding="utf-8"))
    event_manifest, extracted_frames = run_evidence_extraction(
        args.video_path,
        probe,
        output_dir,
        video_learning_scripts,
    )
    intervals = [
        {"id": f"shot-{index:03d}", "start": item["start"], "end": item["end"]}
        for index, item in enumerate(event_manifest["intervals"], start=1)
    ]
    role_names = {"start": "entry", "peak": "peak", "end": "exit"}
    frames = [
        {
            "shot_id": item["event_id"].replace("event", "shot"),
            "role": role_names[item["role"]],
            "timestamp": item["time"],
            "path": item["path"],
        }
        for item in extracted_frames
    ]
    manifest = build_manifest(
        args.video_path,
        probe,
        intervals,
        frames,
    )
    (output_dir / "evidence-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
