import json

import pytest

from scripts.run_skycaptioner import (
    build_structural_prompt,
    parse_model_response,
    prepare_dry_run,
    run_structural_captioning,
)


def _shot(shot_id="source:shot-02", start=4.0):
    return {
        "id": shot_id,
        "timestamps": {"start": start, "end": start + 2.0},
        "evidence": [
            {"role": "entry", "timestamp": start, "path": "frames/entry.jpg"},
            {"role": "peak", "timestamp": start + 1.0, "path": "frames/peak.jpg"},
            {"role": "exit", "timestamp": start + 2.0, "path": "frames/exit.jpg"},
        ],
    }


def test_build_structural_prompt_limits_the_model_to_structural_evidence():
    """Removing field, evidence, or uncertainty instructions must make this test fail."""
    prompt = build_structural_prompt(_shot())

    assert "source:shot-02" in prompt
    assert "entry @ 4.0s: frames/entry.jpg" in prompt
    assert "peak @ 5.0s: frames/peak.jpg" in prompt
    assert "exit @ 6.0s: frames/exit.jpg" in prompt
    assert "shot_type" in prompt
    assert "camera_motion" in prompt
    assert "confidence_note" in prompt
    assert "uncertain" in prompt
    assert "ASR" not in prompt


def test_parse_model_response_preserves_the_source_shot_id_and_uncertainty():
    """Replacing the source id or dropping an explicit uncertainty note must break this test."""
    raw_response = json.dumps(
        {
            "shot_id": "scene-A:take_001",
            "shot_type": "dialogue",
            "shot_size": "medium",
            "angle": "eye-level",
            "camera_position": "front",
            "camera_motion": "uncertain",
            "expression": "neutral",
            "environment": "interior",
            "lighting": "soft",
            "confidence_note": "uncertain: camera movement is not visible in the sampled frames",
        }
    )

    record = parse_model_response(raw_response, "scene-A:take_001")

    assert record["shot_id"] == "scene-A:take_001"
    assert record["camera_motion"] == "uncertain"
    assert record["confidence_note"] == "uncertain: camera movement is not visible in the sampled frames"


def test_parse_model_response_rejects_malformed_or_incomplete_output():
    """Accepting a missing required structural field would hide unsupported inference."""
    malformed = json.dumps(
        {
            "shot_id": "shot-1",
            "shot_type": "action",
            "shot_size": "wide",
            "angle": "eye-level",
            "camera_position": "front",
            "camera_motion": "static",
            "expression": "focused",
            "environment": "street",
        }
    )

    with pytest.raises(ValueError, match="missing required field: lighting"):
        parse_model_response(malformed, "shot-1")

    with pytest.raises(ValueError, match="valid JSON object"):
        parse_model_response("not json", "shot-1")


def test_prepare_dry_run_is_deterministic_and_timestamp_ordered_without_a_backend():
    """Changing ordering, prompt mapping, or importing the backend in dry-run must break this test."""
    manifest = {"shots": [_shot("late-id", 4.0), _shot("early-id", 0.0)]}

    first = prepare_dry_run(
        manifest,
        model_path="D:/models/SkyCaptioner-V1",
        batch_size=2,
        frame_budget=3,
        device="cuda",
    )
    second = prepare_dry_run(
        manifest,
        model_path="D:/models/SkyCaptioner-V1",
        batch_size=2,
        frame_budget=3,
        device="cuda",
    )

    assert first == second
    assert first["mode"] == "dry-run"
    assert first["model_path"] == "D:/models/SkyCaptioner-V1"
    assert first["batch_size"] == 2
    assert first["frame_budget"] == 3
    assert first["device"] == "cuda"
    assert [request["shot_id"] for request in first["requests"]] == ["early-id", "late-id"]
    assert first["requests"][0]["evidence"] == _shot("early-id", 0.0)["evidence"]
    assert "early-id" in first["requests"][0]["prompt"]


def test_run_structural_captioning_keeps_raw_response_and_evidence_with_an_injected_backend():
    """Dropping raw output or evidence references would make structural results unauditable."""
    raw_response = json.dumps(
        {
            "shot_id": "source-id",
            "shot_type": "action",
            "shot_size": "wide",
            "angle": "low",
            "camera_position": "side",
            "camera_motion": "tracking",
            "expression": "determined",
            "environment": "exterior",
            "lighting": "daylight",
        }
    )
    seen_requests = []

    def backend(request):
        seen_requests.append(request)
        return raw_response

    records = run_structural_captioning(
        {"shots": [_shot("source-id", 0.0)]},
        model_path="D:/models/SkyCaptioner-V1",
        batch_size=1,
        frame_budget=3,
        device="cuda",
        backend=backend,
    )

    assert [record["shot_id"] for record in records] == ["source-id"]
    assert records[0]["raw_model_response"] == raw_response
    assert records[0]["evidence"] == _shot("source-id", 0.0)["evidence"]
    assert [request["shot_id"] for request in seen_requests] == ["source-id"]
