# Baseline acceptance record

## Control

- Date: 2026-08-08
- Source: authorized `shot_01_storytime.mp4`
- Control condition: no `video-prompt-reverse` Skill
- Baseline record: an authorized no-Skill control analysis of the source video; it documented media facts, timestamped frames, T2V/I2V prompts, and explicit uncertainty.

## Observed baseline gaps

The control analysis provides useful media facts, timestamped frames, T2V/I2V prompts, and explicit uncertainty. It nevertheless omits required package fields:

1. No five-role review from screenwriter, director, cinematographer, production designer, and editor.
2. No enhanced prompt or three single-variable variants.
3. No structured source-by-source separation before fusion for SkyCaptioner, general VLM, ASR/OCR, and human project context.
4. No reproducible prompt-package schema or validator result.

The control also conflates source reconstruction requirements with generation-stability guidance in its `禁止项`: the baseline explicitly combines constraints derived from the picture with constraints intended to avoid hand, page, and background artifacts. The later Skill must preserve those categories separately.

## Acceptance implication

The Skill must retain the baseline's evidence and uncertainty discipline while producing the omitted structured review, variant, source-separation, and validation fields.

## Deterministic unit and contract status

- Task 2: evidence-manifest construction, schema validation, event bounding, and extraction ordering pass 6 focused tests.
- Task 3: read-only runtime health and static PE/CUDA evidence checks pass 12 focused tests. This is static health only.
- Task 4: SkyCaptioner request/response contracts, frame budgeting, batching, dry-run behavior, and injected execution pass 7 focused tests. No real model was loaded.
- Task 5: four-source fusion and strict prompt-package validation pass 106 focused tests; the repository's post-Task-5 full suite passes 131 tests.

These results establish deterministic unit and contract behavior only. Fresh-agent Skill behavior is a Task 6 controller gate. Real SkyCaptioner/Qwen execution and MiniMax H3 or other generation acceptance remain pending Tasks 7 and 8; executable smoke, visual similarity, and production quality are not yet proven.

## Task 6 forward-test round 1

The authorized fresh-agent run recorded these fields:

- PASS: orchestrator routing, authorization, and declared fixed-interval fallback.
- PASS: four source streams remained separate, including explicit empty streams.
- PASS: all five professional roles were present.
- PASS: source-reconstruction and generation-stability negatives remained separate.
- PASS: uncertainty and validation boundaries were explicit; no model execution or strict-validator result was claimed.
- FAIL: each single-variable variant was only a replacement section plus a reference to seven unchanged baseline sections, not a complete standalone eight-section prompt.

The Skill now requires every variant to print the full canonical prompt with exactly its mapped section changed. A controller-owned fresh-agent rerun is required before recording this field as PASS.
