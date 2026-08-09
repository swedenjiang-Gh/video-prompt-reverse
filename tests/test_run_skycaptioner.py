import json
import sys
from types import SimpleNamespace

import pytest

from scripts.run_skycaptioner import (
    _load_transformers_backend,
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


def test_prepare_dry_run_applies_frame_budget_once_to_evidence_and_prompt():
    """Applying the frame budget after prompt construction would leak unsent evidence."""
    shot = _shot("budgeted", 0.0)
    shot["evidence"].append({"role": "extra", "timestamp": 3.0, "path": "frames/extra.jpg"})

    dry_run = prepare_dry_run(
        {"shots": [shot]},
        model_path="D:/models/SkyCaptioner-V1",
        batch_size=1,
        frame_budget=2,
        device="cuda",
    )

    request = dry_run["requests"][0]
    assert request["evidence"] == shot["evidence"][:2]
    assert "frames/entry.jpg" in request["prompt"]
    assert "frames/peak.jpg" in request["prompt"]
    assert "frames/exit.jpg" not in request["prompt"]
    assert "frames/extra.jpg" not in request["prompt"]


def _raw_response(shot_id):
    return json.dumps(
        {
            "shot_id": shot_id,
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


def test_run_structural_captioning_batches_injected_backend_and_keeps_auditable_records():
    """Calling an injected backend once per shot would make batch_size inert."""
    seen_batches = []

    def backend(requests):
        seen_batches.append(requests)
        if isinstance(requests, dict):
            return _raw_response(requests["shot_id"])
        return [_raw_response(request["shot_id"]) for request in requests]

    records = run_structural_captioning(
        {"shots": [_shot("source-id", 0.0), _shot("second-id", 2.0), _shot("third-id", 4.0)]},
        model_path="D:/models/SkyCaptioner-V1",
        batch_size=2,
        frame_budget=3,
        device="cuda",
        backend=backend,
    )

    assert [record["shot_id"] for record in records] == ["source-id", "second-id", "third-id"]
    assert records[0]["raw_model_response"] == _raw_response("source-id")
    assert records[0]["evidence"] == _shot("source-id", 0.0)["evidence"]
    assert [[request["shot_id"] for request in batch] for batch in seen_batches] == [
        ["source-id", "second-id"],
        ["third-id"],
    ]


def test_transformers_backend_uses_qwen_chat_template_and_decodes_only_new_tokens(tmp_path, monkeypatch):
    """Using plain prompt+images or decoding input prefixes would break Qwen batch responses."""
    class FakeTensor:
        def __init__(self, values):
            self.values = values

        def to(self, device):
            return self

        def __iter__(self):
            return iter(self.values)

        def tolist(self):
            return self.values

    class FakeImageFile:
        def __init__(self, path):
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def convert(self, mode):
            return f"image:{self.path}"

    class FakeProcessor:
        def __init__(self):
            self.chat_messages = []
            self.calls = []
            self.decoded = []

        def apply_chat_template(self, messages, tokenize, add_generation_prompt):
            self.chat_messages.append((messages, tokenize, add_generation_prompt))
            return f"rendered:{len(self.chat_messages)}"

        def __call__(self, *, text, images, return_tensors, padding):
            self.calls.append((text, images, return_tensors, padding))
            return {
                "input_ids": FakeTensor([[1, 2], [3, 4, 5]]),
                "attention_mask": FakeTensor([[1, 1], [1, 1, 1]]),
            }

        def batch_decode(self, generated, skip_special_tokens):
            self.decoded.append((generated, skip_special_tokens))
            return ["response-one", "response-two"]

    class FakeModel:
        def to(self, device):
            return self

        def eval(self):
            return self

        def generate(self, **inputs):
            return [[1, 2, 91], [3, 4, 5, 92]]

    processor = FakeProcessor()
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(float16="fp16", float32="fp32"))
    monkeypatch.setitem(sys.modules, "PIL", SimpleNamespace(Image=SimpleNamespace(open=FakeImageFile)))
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(
            AutoProcessor=SimpleNamespace(from_pretrained=lambda *args, **kwargs: processor),
            AutoModelForVision2Seq=SimpleNamespace(from_pretrained=lambda *args, **kwargs: FakeModel()),
        ),
    )
    model_path = tmp_path / "SkyCaptioner-V1"
    model_path.mkdir()

    backend = _load_transformers_backend(str(model_path), "cuda")
    responses = backend(
        [
            {"prompt": "first", "evidence": _shot("one", 0.0)["evidence"][:2]},
            {"prompt": "second", "evidence": _shot("two", 2.0)["evidence"][:1]},
        ]
    )

    assert responses == ["response-one", "response-two"]
    assert [call[1] for call in processor.chat_messages] == [False, False]
    assert [call[2] for call in processor.chat_messages] == [True, True]
    assert [[item["type"] for item in call[0][0]["content"]] for call in processor.chat_messages] == [
        ["image", "image", "text"],
        ["image", "text"],
    ]
    assert [[item.get("image") for item in call[0][0]["content"]] for call in processor.chat_messages] == [
        ["frames/entry.jpg", "frames/peak.jpg", None],
        ["frames/entry.jpg", None],
    ]
    assert processor.calls == [
        (["rendered:1", "rendered:2"], ["image:frames/entry.jpg", "image:frames/peak.jpg", "image:frames/entry.jpg"], "pt", True)
    ]
    assert processor.decoded == [([[91], [92]], True)]
