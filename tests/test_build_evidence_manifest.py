from pathlib import Path

import pytest

from scripts.build_evidence_manifest import (
    build_manifest,
    normalize_event_intervals,
    run_evidence_extraction,
    validate_manifest,
)


def test_build_manifest_orders_bounded_shots_and_retains_three_evidence_points():
    """Removing sort, bounds checks, or any evidence role must break this test."""
    manifest = build_manifest(
        Path("input/clip.mp4"),
        {
            "duration_seconds": 12.0,
            "width": 1920,
            "height": 1080,
            "fps": 24.0,
        },
        [
            {"id": "shot-2", "start": 4.0, "end": 8.0, "source": "event-scan"},
            {"id": "shot-1", "start": 0.0, "end": 4.0, "source": "event-scan"},
        ],
        [
            {"shot_id": "shot-2", "role": "exit", "timestamp": 7.8, "path": "frames/007800.jpg"},
            {"shot_id": "shot-1", "role": "peak", "timestamp": 2.0, "path": "frames/002000.jpg"},
            {"shot_id": "shot-2", "role": "entry", "timestamp": 4.1, "path": "frames/004100.jpg"},
            {"shot_id": "shot-1", "role": "exit", "timestamp": 3.9, "path": "frames/003900.jpg"},
            {"shot_id": "shot-2", "role": "peak", "timestamp": 6.0, "path": "frames/006000.jpg"},
            {"shot_id": "shot-1", "role": "entry", "timestamp": 0.1, "path": "frames/000100.jpg"},
        ],
    )

    assert manifest["media"] == {
        "video_path": "input/clip.mp4",
        "duration_seconds": 12.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
    }
    assert [shot["id"] for shot in manifest["shots"]] == ["shot-1", "shot-2"]
    assert [shot["timestamps"] for shot in manifest["shots"]] == [
        {"start": 0.0, "end": 4.0},
        {"start": 4.0, "end": 8.0},
    ]
    assert manifest["shots"][0]["evidence"] == [
        {"role": "entry", "timestamp": 0.1, "path": "frames/000100.jpg"},
        {"role": "peak", "timestamp": 2.0, "path": "frames/002000.jpg"},
        {"role": "exit", "timestamp": 3.9, "path": "frames/003900.jpg"},
    ]
    assert manifest["shots"][1]["evidence"] == [
        {"role": "entry", "timestamp": 4.1, "path": "frames/004100.jpg"},
        {"role": "peak", "timestamp": 6.0, "path": "frames/006000.jpg"},
        {"role": "exit", "timestamp": 7.8, "path": "frames/007800.jpg"},
    ]
    assert manifest["source_attribution"] == {
        "intervals": "event-scan",
        "frames": "extracted-frames",
    }


def test_build_manifest_rejects_evidence_outside_its_shot_bounds():
    """Removing evidence timestamp validation must make this test fail."""
    with pytest.raises(ValueError, match="outside shot bounds"):
        build_manifest(
            Path("input/clip.mp4"),
            {"duration_seconds": 4.0, "width": 1920, "height": 1080, "fps": 24.0},
            [{"id": "shot-1", "start": 0.0, "end": 4.0, "source": "event-scan"}],
            [
                {"shot_id": "shot-1", "role": "entry", "timestamp": 0.1, "path": "frames/000100.jpg"},
                {"shot_id": "shot-1", "role": "peak", "timestamp": 2.0, "path": "frames/002000.jpg"},
                {"shot_id": "shot-1", "role": "exit", "timestamp": 4.1, "path": "frames/004100.jpg"},
            ],
        )


def test_normalize_event_intervals_clamps_a_final_event_to_media_duration():
    """Removing the duration clamp must make downstream extraction inconsistent."""
    assert normalize_event_intervals(
        [{"start": 8.0, "peak": 9.5, "end": 11.0, "peak_score": 7.0}],
        10.0,
    ) == [{"start": 8.0, "peak": 9.5, "end": 10.0, "peak_score": 7.0}]


def test_validate_manifest_rejects_malformed_public_schema_instance():
    """Removing public schema checks must allow invalid paths, roles, and extra fields."""
    malformed = {
        "media": {
            "video_path": 42,
            "duration_seconds": 12.0,
            "width": 1920,
            "height": 1080,
            "fps": 24.0,
        },
        "shots": [
            {
                "id": "shot-1",
                "timestamps": {"start": 0.0, "end": 4.0},
                "evidence": [
                    {"role": "entry", "timestamp": 0.1, "path": "frames/000100.jpg"},
                    {"role": "peak", "timestamp": 2.0, "path": "frames/002000.jpg"},
                    {"role": "exit", "timestamp": 3.9, "path": "frames/003900.jpg"},
                ],
                "unexpected": True,
            }
        ],
        "source_attribution": {"intervals": "event-scan", "frames": "extracted-frames"},
    }

    with pytest.raises(ValueError, match="analysis schema"):
        validate_manifest(malformed)


def test_validate_manifest_requires_entry_peak_exit_in_order():
    """Removing the role-structure check must accept duplicate evidence roles."""
    malformed = {
        "media": {
            "video_path": "input/clip.mp4",
            "duration_seconds": 12.0,
            "width": 1920,
            "height": 1080,
            "fps": 24.0,
        },
        "shots": [
            {
                "id": "shot-1",
                "timestamps": {"start": 0.0, "end": 4.0},
                "evidence": [
                    {"role": "entry", "timestamp": 0.1, "path": "frames/000100.jpg"},
                    {"role": "entry", "timestamp": 2.0, "path": "frames/002000.jpg"},
                    {"role": "exit", "timestamp": 3.9, "path": "frames/003900.jpg"},
                ],
            }
        ],
        "source_attribution": {"intervals": "event-scan", "frames": "extracted-frames"},
    }

    with pytest.raises(ValueError, match="entry, peak, and exit"):
        validate_manifest(malformed)


def test_run_evidence_extraction_clamps_manifest_before_frame_extraction(tmp_path):
    """Moving normalization after extraction makes the extractor emit timestamp 11.0."""
    scripts = tmp_path / "video-learning"
    scripts.mkdir()
    (scripts / "scan_events.py").write_text(
        """import json
import sys
from pathlib import Path

output = Path(sys.argv[sys.argv.index('--output') + 1])
output.write_text(json.dumps({'intervals': [{'start': 8.0, 'peak': 9.5, 'end': 11.0}]}), encoding='utf-8')
""",
        encoding="utf-8",
    )
    (scripts / "extract_event_frames.py").write_text(
        """import json
import sys
from pathlib import Path

events = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))['intervals']
print(json.dumps([{'event_id': 'event-001', 'role': 'end', 'time': events[0]['end'], 'path': 'frames/exit.jpg'}]))
""",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _, frames = run_evidence_extraction(
        Path("input/clip.mp4"),
        {"duration_seconds": 10.0},
        output_dir,
        scripts,
    )

    assert frames == [
        {"event_id": "event-001", "role": "end", "time": 10.0, "path": "frames/exit.jpg"}
    ]
