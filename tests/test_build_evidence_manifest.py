from pathlib import Path

import pytest

from scripts.build_evidence_manifest import build_manifest


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
