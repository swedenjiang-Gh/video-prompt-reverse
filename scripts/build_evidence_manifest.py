"""Assemble structured video evidence from video-learning artifacts."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


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

    return {
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a video-prompt-reverse evidence manifest.")
    parser.add_argument("video_path", type=Path)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--task", required=True)
    args = parser.parse_args()

    output_dir = Path("D:/VideoLearning/work") / args.task / "video-prompt-reverse"
    output_dir.mkdir(parents=True, exist_ok=True)
    event_manifest_path = output_dir / "event-manifest.json"
    frame_dir = output_dir / "evidence-frames"
    video_learning_scripts = Path(__file__).resolve().parents[2] / "video-learning" / "scripts"
    subprocess.run(
        [sys.executable, str(video_learning_scripts / "scan_events.py"), str(args.video_path), "--output", str(event_manifest_path)],
        check=True,
    )
    extracted = subprocess.run(
        [sys.executable, str(video_learning_scripts / "extract_event_frames.py"), str(args.video_path), str(event_manifest_path), str(frame_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    event_manifest = json.loads(event_manifest_path.read_text(encoding="utf-8"))
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
        for item in json.loads(extracted.stdout)
    ]
    manifest = build_manifest(
        args.video_path,
        json.loads(args.probe.read_text(encoding="utf-8")),
        intervals,
        frames,
    )
    (output_dir / "evidence-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
