import json
from copy import deepcopy

import pytest

from test_validate_prompt_package import valid_package
from scripts.fuse_prompt_package import (
    _default_runner,
    build_fusion_instruction,
    build_source_references,
    extract_strict_json_object,
    fuse_prompt_package,
    load_records,
    prepare_fusion_dry_run,
    write_prompt_package,
)


def test_build_instruction_keeps_all_four_source_namespaces_separate():
    """Merging any observation stream before fusion must break this test."""
    instruction = build_fusion_instruction(
        evidence_manifest={"media": {"duration_seconds": 2.0}, "shots": []},
        skycaptioner=[{"shot_id": "shot-001", "camera_motion": "static"}],
        general_vlm=[{"shot_id": "shot-001", "observation": "red coat"}],
        asr_ocr=[{"shot_id": "shot-001", "transcript": "hello"}],
        human_context=[{"project": "launch film"}],
        target_engine={"name": "Seedance", "parameters": {"duration": 2}},
        mode="reconstruction",
        generated_at="2026-08-09T10:00:00Z",
    )

    sections = json.loads(instruction.split("SOURCE_INPUTS_JSON\n", 1)[1].split("\nEND_SOURCE_INPUTS_JSON", 1)[0])
    assert sections == {
        "skycaptioner": [{"shot_id": "shot-001", "camera_motion": "static"}],
        "general_vlm": [{"shot_id": "shot-001", "observation": "red coat"}],
        "asr_ocr": [{"shot_id": "shot-001", "transcript": "hello"}],
        "human_context": [{"project": "launch film"}],
    }


def test_extract_strict_json_rejects_malformed_or_ambiguous_model_output():
    """Accepting fences, prefix/suffix prose, or a non-object response must break this test."""
    assert extract_strict_json_object('{"metadata":{"mode":"reconstruction"}}') == {
        "metadata": {"mode": "reconstruction"}
    }

    for raw in (
        'Here is the package: {"metadata": {}}',
        '{"metadata": {}} trailing explanation',
        '```json\n{"metadata": {}}\n```',
        '[{"metadata": {}}]',
        '{"metadata": {}, "metadata": {"mode": "ambiguous"}}',
        '{"metadata": NaN}',
        '{not json}',
    ):
        with pytest.raises(ValueError, match="exactly one JSON object"):
            extract_strict_json_object(raw)


def test_build_source_references_assigns_stable_namespaced_provenance_ids():
    """Using content-derived or cross-namespace IDs would make provenance unstable or ambiguous."""
    source_inputs = {
        "skycaptioner": [{"shot_id": "shot-009"}, {"shot_id": "shot-001"}],
        "general_vlm": [{"observation": "one"}],
        "asr_ocr": [],
        "human_context": [{"project": "one"}],
    }

    assert build_source_references(source_inputs) == {
        "skycaptioner": ["skycaptioner:0001", "skycaptioner:0002"],
        "general_vlm": ["general_vlm:0001"],
        "asr_ocr": [],
        "human_context": ["human_context:0001"],
    }


def test_build_instruction_embeds_the_machine_readable_output_contract():
    """Omitting a required output field from the fusion request must break this test."""
    instruction = build_fusion_instruction(
        evidence_manifest={"media": {"duration_seconds": 1.0}, "shots": []},
        skycaptioner=[],
        general_vlm=[],
        asr_ocr=[],
        human_context=[],
        target_engine={"name": "Seedance", "parameters": {"duration_seconds": 1}},
        mode="reconstruction",
        generated_at="2026-08-09T10:00:00Z",
    )
    contract = json.loads(
        instruction.split("OUTPUT_CONTRACT_JSON\n", 1)[1].split(
            "\nEND_OUTPUT_CONTRACT_JSON", 1
        )[0]
    )

    assert contract["sources"] == [
        "skycaptioner",
        "general_vlm",
        "asr_ocr",
        "human_context",
    ]
    assert contract["five_role_review"] == [
        "screenwriter",
        "director",
        "cinematographer",
        "production_designer",
        "editor",
    ]
    assert contract["prompts"]["single_variable_variant_count"] == 3
    assert contract["prompts"]["standalone_sections"] == [
        "SUBJECT",
        "ACTION",
        "SCENE",
        "CAMERA",
        "LIGHTING",
        "TIMING",
        "AUDIO",
        "CONSTRAINTS",
    ]
    assert contract["strict_json"] == "one bare object with no prefix, suffix, or fences"


def test_fuse_uses_injected_runner_with_argument_array_then_validates_output(capsys):
    """Shell interpolation, an unvalidated response, or logging private paths must break this test."""
    manifest = {
        "media": {
            "video_path": "input/reference.mp4",
            "duration_seconds": 4.0,
            "width": 1920,
            "height": 1080,
            "fps": 24.0,
        },
        "shots": [
            {
                "id": "shot-001",
                "timestamps": {"start": 0.0, "end": 4.0},
                "evidence": [
                    {"role": "entry", "timestamp": 0.0, "path": "evidence/shot-001-entry.jpg"}
                ],
            }
        ],
    }
    sources = {
        "skycaptioner": [{"shot_id": "shot-001"}],
        "general_vlm": [{"shot_id": "shot-001"}],
        "asr_ocr": [{"shot_id": "shot-001"}],
        "human_context": [{"project": "launch"}],
    }
    package = valid_package()
    package["sources"] = build_source_references(sources)
    seen = []

    def runner(arguments, prompt):
        seen.append((arguments, prompt))
        return json.dumps(package)

    result = fuse_prompt_package(
        evidence_manifest=manifest,
        skycaptioner=sources["skycaptioner"],
        general_vlm=sources["general_vlm"],
        asr_ocr=sources["asr_ocr"],
        human_context=sources["human_context"],
        target_engine=package["engine"],
        mode="reconstruction",
        generated_at="2026-08-09T10:00:00Z",
        llama_executable="D:/Private Runtime/llama-cli.exe",
        model_path="D:/Private Models/qwen.gguf",
        runner=runner,
    )

    assert result == package
    assert seen[0][0] == [
        "D:/Private Runtime/llama-cli.exe",
        "-m",
        "D:/Private Models/qwen.gguf",
        "--ctx-size",
        "32768",
        "--temp",
        "0",
        "--no-display-prompt",
    ]
    assert isinstance(seen[0][0], list)
    assert "SOURCE_INPUTS_JSON" in seen[0][1]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_write_outputs_json_and_markdown_only_after_validation(tmp_path):
    """Rendering or writing Markdown before package validation must break this test."""
    invalid = deepcopy(valid_package())
    del invalid["five_role_review"]["editor"]
    with pytest.raises(ValueError, match="five_role_review.*missing"):
        write_prompt_package(invalid, tmp_path)
    assert list(tmp_path.iterdir()) == []

    json_path, markdown_path = write_prompt_package(valid_package(), tmp_path)

    assert json_path.name == "prompt-package.json"
    assert markdown_path.name == "prompt-package.md"
    assert json.loads(json_path.read_text(encoding="utf-8")) == valid_package()
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "[evidence/shot-001-entry.jpg](<evidence/shot-001-entry.jpg>)" in markdown
    assert "## Reconstruction T2V" in markdown
    assert "## Reconstruction I2V" in markdown
    assert "## Enhanced" in markdown
    assert "camera_motion" in markdown


def test_prepare_dry_run_builds_the_request_without_runner_or_private_paths():
    """Calling a runner or exposing local executable/model paths during dry-run must break this test."""
    result = prepare_fusion_dry_run(
        evidence_manifest={"media": {"duration_seconds": 1.0}, "shots": []},
        skycaptioner=[],
        general_vlm=[],
        asr_ocr=[],
        human_context=[],
        target_engine={"name": "Seedance", "parameters": {"duration_seconds": 1}},
        mode="reconstruction",
        generated_at="2026-08-09T10:00:00Z",
    )

    assert result["mode"] == "dry-run"
    assert result["required_source_references"] == {
        "skycaptioner": [],
        "general_vlm": [],
        "asr_ocr": [],
        "human_context": [],
    }
    assert result["argument_template"] == [
        "<llama-executable>",
        "-m",
        "<local-model>",
        "--ctx-size",
        "32768",
        "--temp",
        "0",
        "--no-display-prompt",
    ]
    assert "OUTPUT_CONTRACT_JSON" in result["instruction"]


def test_load_records_accepts_json_arrays_objects_and_skycaptioner_jsonl(tmp_path):
    """Treating JSONL as one malformed JSON document must break the CLI input boundary."""
    array_path = tmp_path / "array.json"
    array_path.write_text('[{"id":"one"},{"id":"two"}]', encoding="utf-8")
    object_path = tmp_path / "object.json"
    object_path.write_text('{"project":"launch"}', encoding="utf-8")
    jsonl_path = tmp_path / "skycaptioner.jsonl"
    jsonl_path.write_text('{"shot_id":"one"}\n{"shot_id":"two"}\n', encoding="utf-8")

    assert load_records(array_path) == [{"id": "one"}, {"id": "two"}]
    assert load_records(object_path) == [{"project": "launch"}]
    assert load_records(jsonl_path) == [{"shot_id": "one"}, {"shot_id": "two"}]


def test_default_runner_passes_an_argument_array_and_prompt_stdin_without_shell(
    tmp_path, monkeypatch, capsys
):
    """Using a command string, shell interpolation, or logging runtime values must break this test."""
    executable = tmp_path / "private llama" / "llama-cli.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"local executable placeholder")
    model = tmp_path / "private model" / "qwen.gguf"
    model.parent.mkdir()
    model.write_bytes(b"local model placeholder")
    arguments = [str(executable), "-m", str(model), "--temp", "0"]
    calls = []

    class Completed:
        returncode = 0
        stdout = '{"ok":true}'

    def fake_run(received_arguments, **kwargs):
        calls.append((received_arguments, kwargs))
        return Completed()

    monkeypatch.setattr("scripts.fuse_prompt_package.subprocess.run", fake_run)

    assert _default_runner(arguments, "private prompt") == '{"ok":true}'
    assert calls == [
        (
            arguments,
            {
                "input": "private prompt",
                "capture_output": True,
                "text": True,
                "shell": False,
                "check": False,
            },
        )
    ]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_fuse_rejects_secret_like_inputs_before_calling_the_runner():
    """Sending credential-shaped source content to the local model must break this test."""
    called = False

    def runner(arguments, prompt):
        nonlocal called
        called = True
        return "{}"

    with pytest.raises(ValueError, match="secret-like key"):
        fuse_prompt_package(
            evidence_manifest={"media": {}, "shots": []},
            skycaptioner=[],
            general_vlm=[],
            asr_ocr=[],
            human_context=[],
            target_engine={"name": "Seedance", "parameters": {"api_key": "not-allowed"}},
            mode="reconstruction",
            generated_at="2026-08-09T10:00:00Z",
            llama_executable="D:/private/llama-cli.exe",
            model_path="D:/private/qwen.gguf",
            runner=runner,
        )
    assert called is False
