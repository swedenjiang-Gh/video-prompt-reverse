import json
from copy import deepcopy
from pathlib import Path

import pytest

from test_validate_prompt_package import valid_package
from scripts.fuse_prompt_package import (
    _default_http_runner,
    assemble_staged_fusion,
    build_fusion_instruction,
    build_fusion_stage_instruction,
    build_source_references,
    canonicalize_prompt_draft,
    extract_strict_json_object,
    fuse_prompt_package,
    load_records,
    normalize_fusion_draft,
    prepare_fusion_dry_run,
    write_prompt_package,
)


def to_fusion_draft(package):
    draft = deepcopy(package)
    attribution_by_ref = {
        entry["prompt_ref"]: entry for entry in draft.pop("attribution")["entries"]
    }

    def structured_prompt(prompt_name, prompt):
        sections = {}
        for line in prompt.splitlines():
            section, value = line.split(":", 1)
            atoms = []
            for index, atom in enumerate(value.strip().split(";"), start=1):
                entry = attribution_by_ref[f"{prompt_name}.{section}.{index:03d}"]
                atoms.append(
                    {
                        "text": atom.strip(),
                        "source_stream": entry["source_stream"],
                        "source_ref": entry["source_ref"],
                        "source_quote": entry["source_quote"],
                        "evidence_refs": entry["evidence_refs"],
                        "status": entry["status"],
                    }
                )
            sections[section] = atoms
        return sections

    prompts = draft["prompts"]
    prompts["reconstruction_t2v"] = structured_prompt(
        "reconstruction_t2v", prompts["reconstruction_t2v"]
    )
    prompts["reconstruction_i2v"] = structured_prompt(
        "reconstruction_i2v", prompts["reconstruction_i2v"]
    )
    prompts["enhanced"] = structured_prompt("enhanced", prompts["enhanced"])
    for index, variant in enumerate(prompts["single_variable_variants"], start=1):
        variant["prompt"] = structured_prompt(f"variant_{index}", variant["prompt"])
    return draft


def to_stage_outputs(package):
    draft = to_fusion_draft(package)
    baseline = draft["prompts"]["reconstruction_t2v"]
    variant_sections = {}
    dimension_sections = {
        "camera_motion": "CAMERA",
        "lighting": "LIGHTING",
        "timing": "TIMING",
    }
    for variant in draft["prompts"]["single_variable_variants"]:
        dimension = variant["changed_dimension"]
        variant_sections[dimension] = variant["prompt"][dimension_sections[dimension]]
    return {
        "base": {
            "five_role_review": draft["five_role_review"],
            "reconstruction_t2v": baseline,
            "anchors": draft["anchors"],
            "negative_constraints": draft["negative_constraints"],
            "uncertainties": draft["uncertainties"],
        },
        "i2v": {"reconstruction_i2v": draft["prompts"]["reconstruction_i2v"]},
        "enhanced": {"enhanced": draft["prompts"]["enhanced"]},
        "variants": variant_sections,
    }


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


def test_stage_instructions_expose_only_the_small_stage_contract():
    """Showing the full package contract to every call would recreate the oversized failure."""
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
    assert "OUTPUT_CONTRACT_JSON" not in instruction
    base = build_fusion_stage_instruction("base", instruction)
    later = build_fusion_stage_instruction(
        "variants", instruction, to_stage_outputs(valid_package())["base"]["reconstruction_t2v"]
    )
    assert "FUSION_STAGE\nbase" in base
    assert "Do not output metadata, media, shots, sources, prompts, engine, attribution" in base
    assert "BASELINE_T2V_JSON" not in base
    assert "FUSION_STAGE\nvariants" in later
    assert "BASELINE_T2V_JSON" in later
    assert "Do not repeat the other seven sections" in later


def test_fuse_runs_four_small_contracts_and_controller_assembles_fixed_fields(capsys):
    """One oversized model response or model-controlled fixed fields must break this test."""
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
        "general_vlm": [
            {
                "shot_id": "shot-001",
                "observation": "A performer crosses the room in one continuous shot.",
            }
        ],
        "asr_ocr": [{"shot_id": "shot-001"}],
        "human_context": [{"project": "launch"}],
    }
    package = valid_package()
    package["sources"] = build_source_references(sources)
    stage_outputs = to_stage_outputs(package)
    seen = []

    def runner(endpoint, prompt):
        seen.append((endpoint, prompt))
        stage = prompt.split("FUSION_STAGE\n", 1)[1].split("\n", 1)[0]
        return json.dumps(stage_outputs[stage])

    result = fuse_prompt_package(
        evidence_manifest=manifest,
        skycaptioner=sources["skycaptioner"],
        general_vlm=sources["general_vlm"],
        asr_ocr=sources["asr_ocr"],
        human_context=sources["human_context"],
        target_engine=package["engine"],
        mode="reconstruction",
        generated_at="2026-08-09T10:00:00Z",
        server_url="http://127.0.0.1:18089",
        runner=runner,
    )

    assert result == package
    assert [prompt.split("FUSION_STAGE\n", 1)[1].split("\n", 1)[0] for _, prompt in seen] == [
        "base",
        "i2v",
        "enhanced",
        "variants",
    ]
    assert all(endpoint == "http://127.0.0.1:18089" for endpoint, _ in seen)
    assert all("SOURCE_INPUTS_JSON" in prompt for _, prompt in seen)
    assert "BASELINE_T2V_JSON" not in seen[0][1]
    assert all("BASELINE_T2V_JSON" in prompt for _, prompt in seen[1:])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_normalize_fusion_draft_builds_prompt_lines_and_attribution_deterministically():
    """Model prose must not control final prompt formatting or attribution row coverage."""
    package = valid_package()
    draft = to_fusion_draft(package)

    assert normalize_fusion_draft(draft) == package

    missing_section = deepcopy(draft)
    del missing_section["prompts"]["enhanced"]["AUDIO"]
    with pytest.raises(ValueError, match="prompt sections"):
        normalize_fusion_draft(missing_section)


def test_canonicalize_prompt_draft_keeps_only_provable_source_support():
    """Model aliases, false quote closure, or unlabelled creative atoms must not reach the package."""
    prompt = to_stage_outputs(valid_package())["base"]["reconstruction_t2v"]
    prompt["SUBJECT"] = [
        {
            "text": "The performer wears a red coat.",
            "source_stream": "general_vlm",
            "source_ref": "general_vlm:0001",
            "source_quote": "red coat",
            "evidence_refs": ["evidence/frame.jpg"],
            "status": "supported",
        }
    ]
    prompt["ACTION"] = [
        {
            "text": "The performer dances.",
            "source_stream": "general_vlm",
            "source_ref": "general_vlm:0001",
            "source_quote": "unrelated claim",
            "evidence_refs": ["evidence/frame.jpg"],
            "status": "supported",
        }
    ]
    prompt["CONSTRAINTS"] = [
        {
            "text": "Keep the wardrobe stable.",
            "source_stream": "none",
            "source_ref": "",
            "source_quote": "",
            "evidence_refs": [],
            "status": "creative",
        }
    ]
    source_inputs = {
        "skycaptioner": [],
        "general_vlm": [
            {
                "observation": "The performer wears a red coat.",
                "evidence_refs": ["evidence/frame.jpg"],
            }
        ],
        "asr_ocr": [],
        "human_context": [],
    }
    required_sources = build_source_references(source_inputs)

    result = canonicalize_prompt_draft(prompt, source_inputs, required_sources)

    assert result["SUBJECT"][0]["status"] == "source-supported"
    assert result["ACTION"][0] == {
        "text": "conservative inferred choice: The performer dances.",
        "source_stream": "none",
        "source_ref": None,
        "source_quote": None,
        "evidence_refs": [],
        "status": "conservative-inferred",
    }
    assert result["CONSTRAINTS"][0]["text"] == (
        "creative choice: Keep the wardrobe stable."
    )
    assert result["CONSTRAINTS"][0]["source_ref"] is None


def test_assemble_replaces_unchanged_model_variants_with_declared_creative_changes():
    """A copied baseline section is not a single-variable variant and needs no model retry."""
    package = valid_package()
    stage_outputs = to_stage_outputs(package)
    baseline = stage_outputs["base"]["reconstruction_t2v"]
    section_by_dimension = {"camera_motion": "CAMERA", "lighting": "LIGHTING", "timing": "TIMING"}
    for dimension, section in section_by_dimension.items():
        stage_outputs["variants"][dimension] = deepcopy(baseline[section])
    sources = {
        "skycaptioner": [],
        "general_vlm": [
            {
                "shot_id": "shot-001",
                "observation": "A performer crosses the room in one continuous shot.",
            }
        ],
        "asr_ocr": [],
        "human_context": [],
    }
    manifest = {
        "media": {
            "duration_seconds": 4.0,
            "width": 1920,
            "height": 1080,
            "fps": 24.0,
        },
        "shots": [
            {
                "id": "shot-001",
                "timestamps": {"start": 0.0, "end": 4.0},
                "evidence": [{"path": "evidence/shot-001-entry.jpg"}],
            }
        ],
    }

    result = assemble_staged_fusion(
        stage_outputs=stage_outputs,
        evidence_manifest=manifest,
        source_inputs=sources,
        required_sources=build_source_references(sources),
        target_engine=package["engine"],
        mode="reconstruction",
        generated_at="2026-08-09T10:00:00Z",
    )

    for variant in result["prompts"]["single_variable_variants"]:
        changed_section = section_by_dimension[variant["changed_dimension"]]
        changed_line = next(
            line for line in variant["prompt"].splitlines() if line.startswith(changed_section)
        )
        assert "creative choice:" in changed_line


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
    assert result["endpoint_template"] == "http://127.0.0.1:<port>/v1/chat/completions"
    assert "OUTPUT_CONTRACT_JSON" not in result["instruction"]
    assert "SOURCE_INPUTS_JSON" in result["instruction"]


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


def test_default_http_runner_returns_only_the_assistant_content(monkeypatch, capsys):
    """The HTTP envelope must not contaminate the strict model JSON body."""
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}'

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return Response()

    monkeypatch.setattr("scripts.fuse_prompt_package.urlopen", fake_urlopen)

    assert _default_http_runner("http://127.0.0.1:18089", "private prompt") == '{"ok":true}'
    assert calls[0][0].full_url == "http://127.0.0.1:18089/v1/chat/completions"
    body = json.loads(calls[0][0].data)
    assert body["messages"][-1]["content"] == "private prompt"
    assert body["response_format"] == {"type": "json_object"}
    assert calls[0][1] == 3600
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
            server_url="http://127.0.0.1:18089",
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
                    "video_path": "C:/Users/ExampleUser/private/reference.mp4",
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
        ("reconstruction", "C:/Users/ExampleUser/private/generated-at", "private path"),
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
        ("reconstruction", "C:/Users/ExampleUser/private/generated-at", "private path"),
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
            server_url="http://127.0.0.1:18089",
            runner=forbidden_runner,
        )
