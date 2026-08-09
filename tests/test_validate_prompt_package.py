from copy import deepcopy

import pytest

from scripts.validate_prompt_package import validate_prompt_package


def complete_prompt(label: str) -> str:
    return "\n".join(
        (
            f"SUBJECT: {label} subject with fixed wardrobe and appearance.",
            "ACTION: Performs the full visible action from start to finish.",
            "SCENE: Defined environment, props, spatial relationships, and background.",
            "CAMERA: Shot size, angle, lens behavior, movement, and composition.",
            "LIGHTING: Direction, quality, color, atmosphere, and visual style.",
            "TIMING: Ordered beats and duration for the complete shot.",
            "AUDIO: Dialogue, sound effects, ambience, and synchronization.",
            "CONSTRAINTS: Preserve anchors and avoid all listed negative constraints.",
        )
    )


def valid_package() -> dict:
    return {
        "metadata": {"mode": "reconstruction", "generated_at": "2026-08-09T10:00:00Z"},
        "media": {"duration_seconds": 4.0, "width": 1920, "height": 1080, "fps": 24.0},
        "shots": [
            {
                "id": "shot-001",
                "timestamps": {"start": 0.0, "end": 4.0},
                "evidence_refs": ["evidence/shot-001-entry.jpg"],
                "description": "A performer crosses the room in one continuous shot.",
            }
        ],
        "sources": {
            "skycaptioner": ["skycaptioner:shot-001"],
            "general_vlm": ["general_vlm:shot-001"],
            "asr_ocr": ["asr_ocr:shot-001"],
            "human_context": ["human_context:0001"],
        },
        "five_role_review": {
            "screenwriter": "The action has a clear beginning, turn, and end.",
            "director": "Blocking and performance intent are explicit.",
            "cinematographer": "Framing, lens behavior, and movement are reproducible.",
            "production_designer": "Wardrobe, props, palette, and environment are anchored.",
            "editor": "Beat timing and continuity points are explicit.",
        },
        "prompts": {
            "reconstruction_t2v": complete_prompt("reconstruction T2V"),
            "reconstruction_i2v": complete_prompt("reconstruction I2V"),
            "enhanced": complete_prompt("enhanced"),
            "single_variable_variants": [
                {"changed_dimension": "camera_motion", "prompt": complete_prompt("camera variant")},
                {"changed_dimension": "lighting", "prompt": complete_prompt("lighting variant")},
                {"changed_dimension": "timing", "prompt": complete_prompt("timing variant")},
            ],
        },
        "engine": {
            "name": "Seedance",
            "parameters": {"duration_seconds": 4, "aspect_ratio": "16:9"},
            "compatibility_notes": ["Use image conditioning only for the I2V prompt."],
        },
        "anchors": ["The performer's red coat remains unchanged."],
        "negative_constraints": {
            "reconstruction_source": ["Do not invent off-screen objects."],
            "generation_stability": ["No identity drift or duplicate limbs."],
        },
        "uncertainties": ["The sampled frames do not prove the exact focal length."],
    }


def test_validate_requires_exactly_the_five_named_review_roles():
    """Dropping a discipline or accepting an invented sixth role must break this test."""
    missing = deepcopy(valid_package())
    del missing["five_role_review"]["editor"]
    with pytest.raises(ValueError, match="five_role_review.*missing"):
        validate_prompt_package(missing)

    extra = deepcopy(valid_package())
    extra["five_role_review"]["sound_designer"] = "Not one of the contracted review roles."
    with pytest.raises(ValueError, match="five_role_review.*extra"):
        validate_prompt_package(extra)

    validate_prompt_package(valid_package())


def test_validate_rejects_missing_or_extra_contract_fields():
    """Silently ignoring a missing section or model-invented field must break this test."""
    missing = deepcopy(valid_package())
    del missing["anchors"]
    with pytest.raises(ValueError, match="prompt package.*missing"):
        validate_prompt_package(missing)

    extra = deepcopy(valid_package())
    extra["model_commentary"] = "uncontracted prose"
    with pytest.raises(ValueError, match="prompt package.*extra"):
        validate_prompt_package(extra)

    nested_extra = deepcopy(valid_package())
    nested_extra["engine"]["model_path"] = "models/local.gguf"
    with pytest.raises(ValueError, match="engine.*extra"):
        validate_prompt_package(nested_extra)


def test_validate_requires_three_unique_single_variable_variants():
    """Accepting fewer variants, duplicate dimensions, or a second change field must break this test."""
    too_few = deepcopy(valid_package())
    too_few["prompts"]["single_variable_variants"].pop()
    with pytest.raises(ValueError, match="exactly three"):
        validate_prompt_package(too_few)

    duplicate = deepcopy(valid_package())
    duplicate["prompts"]["single_variable_variants"][1]["changed_dimension"] = "camera_motion"
    with pytest.raises(ValueError, match="unique changed_dimension"):
        validate_prompt_package(duplicate)

    ambiguous = deepcopy(valid_package())
    ambiguous["prompts"]["single_variable_variants"][0]["also_changed"] = "lighting"
    with pytest.raises(ValueError, match="variant.*extra"):
        validate_prompt_package(ambiguous)


def test_validate_requires_every_prompt_to_be_complete_and_standalone():
    """Accepting a blank section or a variant that says 'same as above' must break this test."""
    incomplete = deepcopy(valid_package())
    incomplete["prompts"]["enhanced"] = incomplete["prompts"]["enhanced"].replace(
        "AUDIO: Dialogue, sound effects, ambience, and synchronization.\n", ""
    )
    with pytest.raises(ValueError, match="enhanced.*AUDIO"):
        validate_prompt_package(incomplete)

    shorthand = deepcopy(valid_package())
    shorthand["prompts"]["single_variable_variants"][0]["prompt"] = (
        "Same as reconstruction_t2v, but use a tracking camera."
    )
    with pytest.raises(ValueError, match="variant 0 prompt.*SUBJECT"):
        validate_prompt_package(shorthand)

    blank = deepcopy(valid_package())
    blank["prompts"]["reconstruction_i2v"] = " "
    with pytest.raises(ValueError, match="reconstruction_i2v.*non-empty"):
        validate_prompt_package(blank)


def test_validate_rejects_reordered_overlapping_or_out_of_bounds_shots():
    """Accepting model-reordered or media-out-of-bounds timestamps must break this test."""
    reordered = deepcopy(valid_package())
    reordered["media"]["duration_seconds"] = 8.0
    second = deepcopy(reordered["shots"][0])
    second["id"] = "shot-002"
    second["timestamps"] = {"start": 4.0, "end": 8.0}
    reordered["shots"] = [second, reordered["shots"][0]]
    with pytest.raises(ValueError, match="chronological"):
        validate_prompt_package(reordered)

    overlapping = deepcopy(valid_package())
    overlapping["media"]["duration_seconds"] = 8.0
    second = deepcopy(overlapping["shots"][0])
    second["id"] = "shot-002"
    second["timestamps"] = {"start": 3.5, "end": 8.0}
    overlapping["shots"].append(second)
    with pytest.raises(ValueError, match="overlap"):
        validate_prompt_package(overlapping)

    out_of_bounds = deepcopy(valid_package())
    out_of_bounds["shots"][0]["timestamps"]["end"] = 4.1
    with pytest.raises(ValueError, match="media bounds"):
        validate_prompt_package(out_of_bounds)


def test_validate_rejects_shot_or_source_provenance_loss_against_inputs():
    """Dropping an input source or replacing an evidence reference must break this test."""
    manifest = {
        "media": {"duration_seconds": 4.0, "width": 1920, "height": 1080, "fps": 24.0},
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
    required_sources = deepcopy(valid_package()["sources"])
    validate_prompt_package(
        valid_package(), evidence_manifest=manifest, required_sources=required_sources
    )

    missing_source = deepcopy(valid_package())
    missing_source["sources"]["general_vlm"] = []
    with pytest.raises(ValueError, match="source provenance"):
        validate_prompt_package(
            missing_source, evidence_manifest=manifest, required_sources=required_sources
        )

    wrong_shot = deepcopy(valid_package())
    wrong_shot["shots"][0]["id"] = "shot-009"
    with pytest.raises(ValueError, match="manifest shot order"):
        validate_prompt_package(
            wrong_shot, evidence_manifest=manifest, required_sources=required_sources
        )

    wrong_evidence = deepcopy(valid_package())
    wrong_evidence["shots"][0]["evidence_refs"] = ["evidence/invented.jpg"]
    with pytest.raises(ValueError, match="evidence provenance"):
        validate_prompt_package(
            wrong_evidence, evidence_manifest=manifest, required_sources=required_sources
        )


def test_validate_keeps_engine_parameters_structured_and_out_of_prompt_prose():
    """Accepting parameter prose or CLI flags inside prompt text must break this test."""
    prose_parameters = deepcopy(valid_package())
    prose_parameters["engine"]["parameters"] = "duration=4, aspect_ratio=16:9"
    with pytest.raises(ValueError, match="engine.parameters.*object"):
        validate_prompt_package(prose_parameters)

    empty_parameters = deepcopy(valid_package())
    empty_parameters["engine"]["parameters"] = {}
    with pytest.raises(ValueError, match="engine.parameters.*non-empty"):
        validate_prompt_package(empty_parameters)

    embedded_flags = deepcopy(valid_package())
    embedded_flags["prompts"]["reconstruction_t2v"] += "\n--duration 4 --aspect-ratio 16:9"
    with pytest.raises(ValueError, match="engine parameter syntax"):
        validate_prompt_package(embedded_flags)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda package: package["engine"]["parameters"].update(
                {"api_key": "sk-examplevalue1234567890"}
            ),
            "secret-like key",
        ),
        (
            lambda package: package["uncertainties"].append(
                "Authorization: Bearer abcdefghijklmnopqrstuvwxyz"
            ),
            "secret-like value",
        ),
        (
            lambda package: package["five_role_review"].update(
                {"editor": "Review stored at C:\\Users\\J\\private\\notes.txt"}
            ),
            "private path",
        ),
    ],
)
def test_validate_rejects_credentials_and_private_machine_paths(mutate, message):
    """Allowing raw credentials or local roots anywhere in a package must break this test."""
    package = valid_package()
    mutate(package)
    with pytest.raises(ValueError, match=message):
        validate_prompt_package(package)


def test_validate_requires_mode_and_timezone_aware_generation_time():
    """Accepting missing, blank, or timezone-free package metadata must break this test."""
    missing = deepcopy(valid_package())
    del missing["metadata"]["mode"]
    with pytest.raises(ValueError, match="metadata.*missing"):
        validate_prompt_package(missing)

    blank_mode = deepcopy(valid_package())
    blank_mode["metadata"]["mode"] = " "
    with pytest.raises(ValueError, match="metadata.mode.*non-empty"):
        validate_prompt_package(blank_mode)

    local_time = deepcopy(valid_package())
    local_time["metadata"]["generated_at"] = "2026-08-09T10:00:00"
    with pytest.raises(ValueError, match="generated_at.*timezone"):
        validate_prompt_package(local_time)


def test_validate_keeps_source_constraints_separate_from_generation_negatives():
    """Collapsing reconstruction fidelity and generation stability into one list must break this test."""
    merged = deepcopy(valid_package())
    merged["negative_constraints"] = [
        "Do not invent off-screen objects.",
        "No identity drift or duplicate limbs.",
    ]
    with pytest.raises(ValueError, match="negative_constraints.*object"):
        validate_prompt_package(merged)

    missing_category = deepcopy(valid_package())
    del missing_category["negative_constraints"]["generation_stability"]
    with pytest.raises(ValueError, match="negative_constraints.*missing"):
        validate_prompt_package(missing_category)

    empty_category = deepcopy(valid_package())
    empty_category["negative_constraints"]["reconstruction_source"] = []
    with pytest.raises(ValueError, match="reconstruction_source.*non-empty"):
        validate_prompt_package(empty_category)


def test_validate_requires_portable_evidence_references_and_described_shots():
    """Allowing empty, parent-traversing, or undescribed shot evidence must break this test."""
    no_evidence = deepcopy(valid_package())
    no_evidence["shots"][0]["evidence_refs"] = []
    with pytest.raises(ValueError, match="evidence_refs.*non-empty"):
        validate_prompt_package(no_evidence)

    traversal = deepcopy(valid_package())
    traversal["shots"][0]["evidence_refs"] = ["../private/frame.jpg"]
    with pytest.raises(ValueError, match="evidence_refs.*portable"):
        validate_prompt_package(traversal)

    blank_description = deepcopy(valid_package())
    blank_description["shots"][0]["description"] = " "
    with pytest.raises(ValueError, match="description.*non-empty"):
        validate_prompt_package(blank_description)


def test_validate_rejects_cross_namespace_source_references():
    """Moving a SkyCaptioner reference into the general-VLM namespace must break this test."""
    crossed = deepcopy(valid_package())
    crossed["sources"]["general_vlm"] = ["skycaptioner:shot-001"]
    with pytest.raises(ValueError, match="general_vlm.*namespace"):
        validate_prompt_package(crossed)


def test_validate_rejects_invalid_media_anchors_and_uncertainty_types():
    """Accepting unusable media dimensions or unstructured anchor lists must break this test."""
    bad_media = deepcopy(valid_package())
    bad_media["media"]["width"] = "1920"
    with pytest.raises(ValueError, match="media.width.*positive integer"):
        validate_prompt_package(bad_media)

    no_anchors = deepcopy(valid_package())
    no_anchors["anchors"] = []
    with pytest.raises(ValueError, match="anchors.*non-empty"):
        validate_prompt_package(no_anchors)

    prose_uncertainty = deepcopy(valid_package())
    prose_uncertainty["uncertainties"] = "No uncertainty."
    with pytest.raises(ValueError, match="uncertainties.*list"):
        validate_prompt_package(prose_uncertainty)


def test_validate_preserves_requested_metadata_media_and_engine_context():
    """Changing the requested mode, manifest media facts, or engine settings must break this test."""
    manifest = {
        "media": {
            "video_path": "input/reference.mp4",
            "duration_seconds": 4.0,
            "width": 1920,
            "height": 1080,
            "fps": 24.0,
        },
        "shots": [],
    }
    expected_engine = deepcopy(valid_package()["engine"])

    wrong_mode = valid_package()
    wrong_mode["metadata"]["mode"] = "enhanced"
    with pytest.raises(ValueError, match="requested metadata"):
        validate_prompt_package(
            wrong_mode,
            expected_mode="reconstruction",
            expected_generated_at="2026-08-09T10:00:00Z",
        )

    wrong_media = valid_package()
    wrong_media["media"]["fps"] = 30.0
    with pytest.raises(ValueError, match="manifest media"):
        validate_prompt_package(wrong_media, evidence_manifest=manifest)

    wrong_engine = valid_package()
    wrong_engine["engine"]["parameters"]["duration_seconds"] = 8
    with pytest.raises(ValueError, match="target engine"):
        validate_prompt_package(wrong_engine, target_engine=expected_engine)

    validate_prompt_package(
        valid_package(),
        target_engine={
            "name": expected_engine["name"],
            "parameters": expected_engine["parameters"],
        },
    )
