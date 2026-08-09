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
    """Shorthand model instructions must not omit binding fields, types, or invariants."""
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

    assert contract["objects"] == {
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
    }
    assert contract["types"] == {
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
    }
    assert contract["prompt_format"] == {
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
    }
    assert contract["strict_json"] == (
        "one bare RFC 8259 object; no duplicate keys, non-finite numbers, prefix, suffix, or fences"
    )
    assert contract["invariants"] == [
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
    ]


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
    assert r"[evidence/shot\-001\-entry\.jpg](<evidence/shot-001-entry.jpg>)" in markdown
    assert "## Reconstruction T2V" in markdown
    assert "## Reconstruction I2V" in markdown
    assert "## Enhanced" in markdown
    assert r"camera\_motion" in markdown


def test_markdown_encodes_evidence_targets_and_escapes_structural_text(tmp_path):
    """Raw Markdown insertion would turn brackets, newlines, or fragments into active structure."""
    package = valid_package()
    package["shots"][0]["evidence_refs"] = ["evidence/final [frame] #1.jpg"]
    package["shots"][0]["description"] = "A [label](https://example.test)\n# injected heading"
    package["five_role_review"]["editor"] = "> quote [cut]"
    package["anchors"] = ["- nested item"]

    _, markdown_path = write_prompt_package(package, tmp_path)
    markdown = markdown_path.read_text(encoding="utf-8")

    assert (
        "[evidence/final \\[frame\\] \\#1\\.jpg]"
        "(<evidence/final%20%5Bframe%5D%20%231.jpg>)"
    ) in markdown
    assert "A \\[label\\]\\(https://example\\.test\\)&#10;\\# injected heading" in markdown
    assert "\\> quote \\[cut\\]" in markdown
    assert "\\- nested item" in markdown
    assert "\n# injected heading" not in markdown


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


@pytest.mark.parametrize(
    "raw",
    [
        '{"id":"one","id":"two"}',
        '{"score":NaN}',
        '{"score":1e999}',
        '{"id":"one"}\n{"score":1e999}\n',
    ],
)
def test_load_records_rejects_duplicate_keys_and_non_finite_json(tmp_path, raw):
    """Falling back from invalid JSON to permissive JSONL must not bypass strict parsing."""
    path = tmp_path / "observations.json"
    path.write_text(raw, encoding="utf-8")

    with pytest.raises(ValueError, match="strict JSON"):
        load_records(path)


def test_instruction_serialization_rejects_non_finite_source_values():
    """Allowing json.dumps to emit NaN would send non-standard JSON to the model."""
    with pytest.raises(ValueError, match="strict JSON"):
        build_fusion_instruction(
            evidence_manifest={"media": {"duration_seconds": 1.0}, "shots": []},
            skycaptioner=[{"confidence": float("nan")}],
            general_vlm=[],
            asr_ocr=[],
            human_context=[],
            target_engine={"name": "Seedance", "parameters": {"duration_seconds": 1}},
            mode="reconstruction",
            generated_at="2026-08-09T10:00:00Z",
        )


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


def test_prepare_allows_legitimate_token_count_metadata():
    """Substring matching on 'token' would reject harmless engine capacity metadata."""
    request = prepare_fusion_dry_run(
        evidence_manifest={"media": {"duration_seconds": 1.0}, "shots": []},
        skycaptioner=[],
        general_vlm=[],
        asr_ocr=[],
        human_context=[],
        target_engine={
            "name": "Seedance",
            "parameters": {"duration_seconds": 1, "token_count": 128},
        },
        mode="reconstruction",
        generated_at="2026-08-09T10:00:00Z",
    )

    assert request["mode"] == "dry-run"


@pytest.mark.parametrize(
    ("evidence_manifest", "human_context", "message"),
    [
        (
            {
                "media": {
                    "video_path": "C:/Users/J/private/reference.mp4",
                    "duration_seconds": 1.0,
                },
                "shots": [],
            },
            [],
            "private path",
        ),
        (
            {"media": {"duration_seconds": 1.0}, "shots": []},
            [{"note": "github_pat_abcdefghijklmnopqrstuvwxyz123456"}],
            "secret-like value",
        ),
    ],
)
def test_prepare_rejects_private_roots_and_common_credentials_before_instruction(
    evidence_manifest, human_context, message
):
    """A dry-run request must not serialize sensitive inputs before checking them."""
    with pytest.raises(ValueError, match=message):
        prepare_fusion_dry_run(
            evidence_manifest=evidence_manifest,
            skycaptioner=[],
            general_vlm=[],
            asr_ocr=[],
            human_context=human_context,
            target_engine={"name": "Seedance", "parameters": {"duration_seconds": 1}},
            mode="reconstruction",
            generated_at="2026-08-09T10:00:00Z",
        )


@pytest.mark.parametrize(
    ("mode", "generated_at", "message"),
    [
        ("api_key=credential-shaped-mode", "2026-08-09T10:00:00Z", "secret-like value"),
        ("reconstruction", "C:/Users/J/private/generated-at", "private path"),
    ],
)
def test_prepare_rejects_sensitive_metadata_before_building_instruction(
    monkeypatch, mode, generated_at, message
):
    """Sensitive metadata must stop dry-run construction before any instruction exists."""
    def forbidden_instruction(**kwargs):
        pytest.fail("instruction builder must not be called")

    monkeypatch.setattr(
        "scripts.fuse_prompt_package.build_fusion_instruction", forbidden_instruction
    )

    with pytest.raises(ValueError, match=message):
        prepare_fusion_dry_run(
            evidence_manifest={"media": {"duration_seconds": 1.0}, "shots": []},
            skycaptioner=[],
            general_vlm=[],
            asr_ocr=[],
            human_context=[],
            target_engine={"name": "Seedance", "parameters": {"duration_seconds": 1}},
            mode=mode,
            generated_at=generated_at,
        )


@pytest.mark.parametrize(
    ("mode", "generated_at", "message"),
    [
        ("api_key=credential-shaped-mode", "2026-08-09T10:00:00Z", "secret-like value"),
        ("reconstruction", "C:/Users/J/private/generated-at", "private path"),
    ],
)
def test_fuse_rejects_sensitive_metadata_before_calling_runner(
    mode, generated_at, message
):
    """Sensitive metadata must stop fusion before the injected runner can execute."""
    def forbidden_runner(arguments, prompt):
        pytest.fail("runner must not be called")

    with pytest.raises(ValueError, match=message):
        fuse_prompt_package(
            evidence_manifest={"media": {"duration_seconds": 1.0}, "shots": []},
            skycaptioner=[],
            general_vlm=[],
            asr_ocr=[],
            human_context=[],
            target_engine={"name": "Seedance", "parameters": {"duration_seconds": 1}},
            mode=mode,
            generated_at=generated_at,
            llama_executable="D:/private/llama-cli.exe",
            model_path="D:/private/qwen.gguf",
            runner=forbidden_runner,
        )
