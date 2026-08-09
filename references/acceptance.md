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

The Skill now requires every variant to print the full canonical prompt with exactly its mapped section changed. Round 2 below closes structural completeness only; semantic coherence remains open.

## Task 6 forward-test round 2

The authorized fresh-agent rerun recorded these portable results:

- PASS: `skycaptioner`, `general_vlm`, `asr_ocr`, and `human_context` remained separate, with all empty streams explicit.
- PASS: all five professional roles were present.
- PASS: reconstruction T2V, reconstruction I2V, and enhanced prompts were present.
- PARTIAL: all three single-variable variants were standalone prompts with all eight canonical sections in order, and their literal changes were limited to the declared mapped sections.
- FAIL: Variant A changed `CAMERA` to a locked composition while its unchanged `TIMING` still required a gradual framing change. The variant was not semantically coherent with its unchanged sections.
- PASS: source-reconstruction and generation-stability negatives remained separate.
- PASS: no model was downloaded or executed and no generation task was submitted.
- PASS: strict machine fusion and prompt-package validation were explicitly reported as pending, not inferred from static analysis.
- FAIL: the UI default prompt invoked `$video-prompt-reverse` directly instead of entering through `$media-studio-orchestrator` first.

Round 2 is partial and does not pass the Task 6 Skill behavior gate. A fresh-agent rerun must prove orchestrator-first entry and semantic compatibility between each changed section and all seven unchanged sections. Real model execution, strict machine fusion/validation, generation similarity, and production quality remain outside this evidence boundary.

## Task 6 forward-test round 3

The authorized fresh-agent rerun recorded these portable results:

- PASS: the route entered through `media-studio-orchestrator` before selecting `video-learning` and `video-prompt-reverse`.
- PASS: `skycaptioner`, `general_vlm`, `asr_ocr`, and `human_context` remained separate, with empty streams explicit.
- PASS: all five professional roles were present.
- PASS: reconstruction T2V, reconstruction I2V, and enhanced prompts were present.
- PASS: all three variants were standalone prompts with all eight canonical sections in order. They changed only `CAMERA`, `LIGHTING`, and `ACTION`, respectively.
- PARTIAL: baseline `TIMING` required neither camera reframing nor an exact-timed gesture, so the locked-camera variant removed the Round 2 contradiction.
- FAIL: Variant C changed `ACTION` to pause and resume reading, while its unchanged `TIMING` still required reading and listening to remain continuous. The baseline sections were not fully orthogonal.
- PASS: source-reconstruction and generation-stability negatives remained separate.
- PASS: no model was downloaded or executed and no generation task was submitted.
- PASS: strict model-backed fusion, prompt-package JSON validation, generation similarity, and production quality were explicitly reported as pending.

Round 3 is partial and does not pass the semantic-variant field. A fresh-agent rerun must show orthogonal baseline sections and semantic compatibility for every unchanged section. Real model execution, strict machine fusion/validation, generated-video similarity, and production quality remain outside this evidence boundary.

## Task 6 forward-test round 4

The authorized fresh-agent rerun recorded these portable results:

- PASS: the route entered through `media-studio-orchestrator` before selecting `video-learning` and `video-prompt-reverse`.
- PASS: `skycaptioner`, `general_vlm`, `asr_ocr`, and `human_context` remained explicit and separate; empty, rejected, or human-only evidence was not reassigned to another stream.
- PASS: all five professional roles were present.
- PASS: reconstruction T2V, reconstruction I2V, and enhanced prompts were present.
- PASS: all three variants were standalone prompts with all eight canonical sections in order. They changed only `CAMERA`, `LIGHTING`, and `ACTION`, respectively.
- PARTIAL: canonical `TIMING` remained limited to duration, pacing, and cuts and introduced no cross-section dependency.
- FAIL: baseline `SCENE` prescribed lit/warm illumination states, while `LIGHTING` prescribed increasing background defocus. Illumination leaked into `SCENE`, and focus/depth leaked into `LIGHTING`, conflicting with the locked/no-rack-focus `CAMERA` variant.
- PASS: source-reconstruction and generation-stability negatives remained separate.
- PASS: model execution, strict prompt-package JSON validation, generation similarity, and production quality were explicitly reported as pending; no model was downloaded or executed and no generation task was submitted.
- PARTIAL: the expected evidence-extraction script root was unavailable, so the standard runtime pipeline was not rerun. The authorized source and previously saved evidence were rechecked instead.

Round 4 is partial and does not pass the cross-section semantic lint field. A fresh-agent rerun must show that every baseline clause has exactly one owner and remains compatible with all unchanged variant sections. Runtime evidence extraction, real model-backed fusion, strict machine validation, generated-video similarity, and production quality remain outside this acceptance boundary.

## Task 6 forward-test round 5

An independent neutral fresh-agent run with no prior implementation or review context recorded these portable results:

- PASS: the route entered through `media-studio-orchestrator` before selecting `video-prompt-reverse`.
- PASS: `skycaptioner`, `general_vlm`, `asr_ocr`, and `human_context` remained explicit and separate, including empty streams for steps that were not run.
- PASS: all five professional roles were present.
- PASS: reconstruction T2V, reconstruction I2V, and enhanced prompts were present.
- FAIL: the baseline did not obey exact canonical ownership. `CAMERA` repeated a no-cut rule already owned by `TIMING`, and `SCENE` repeated a readable-text prohibition already owned by `CONSTRAINTS`.
- PARTIAL: the three standalone variants each contained all eight canonical sections and changed only `CAMERA`, `LIGHTING`, or `ACTION`, respectively. Their changed sections remained semantically compatible with the seven unchanged sections, but every variant cloned the two baseline ownership duplicates.
- PASS: source-reconstruction and generation-stability negatives remained separate.
- PASS: the proof boundary remained explicit. Standard model-backed fusion, strict prompt-package JSON validation, model execution, generated-video similarity, and production quality were reported as pending; no model was downloaded or executed and no generation task was submitted.

Round 5 is partial/FAIL and does not pass the Task 6 fresh-agent Skill behavior gate for cross-section ownership. The ownership guidance now assigns all cut/editing declarations only to `TIMING` and all readable-text prohibitions only to `CONSTRAINTS`; a new independent fresh-agent rerun must demonstrate those boundaries before this gate can pass. Runtime model fusion, strict machine validation, executable generation, visual similarity, and production quality remain separate acceptance gates.

## Task 6 forward-test round 6c

The authorized fresh-agent rerun recorded these portable results:

- PASS: the route, authorization boundary, four separate source streams, five-role review, complete prompt set, standalone eight-section variants, separated negative categories, and proof limits remained explicit.
- PASS: cut and single-take clauses stayed in `TIMING`, and readable-text prohibitions stayed in `CONSTRAINTS`.
- FAIL: source audio remained unresolved, but reconstruction prompts prescribed specific ambience and action-synchronized sounds. An `ACTION`-only variant then added the matching action while cloning the same sound in unchanged `AUDIO`.
- FAIL: the enhanced prompt placed event emergence and reactions in `ACTION` but repeated the event state in `SCENE` and its progression in `TIMING`; only emitted illumination belonged in `LIGHTING`.
- PASS: no model-backed fusion, strict JSON validation, generation, rendered similarity, or production-quality result was claimed.

Round 6c is partial/FAIL and does not pass the source-evidence or canonical-ownership behavior gates. Reconstruction audio must remain explicitly unresolved until evidence resolves it, and the clause-ownership lint must pass independently for reconstruction, enhanced, and variant prompts. A new independent fresh-agent rerun must demonstrate both behaviors before Task 6 can pass.

## Task 6 forward-test round 7

The authorized fresh-agent rerun recorded these portable results:

- PASS: orchestrator routing, four separate source streams, five-role review, complete reconstruction/enhanced prompts, standalone single-variable variants, unresolved reconstruction audio, separated negative categories, and proof-level boundaries remained explicit.
- PASS: the earlier cut/readable-text and reconstruction-audio ownership fixes remained intact.
- FAIL: fixed-coverage frames and empty event intervals established only sampled framing states, but reconstruction `CAMERA` prescribed a definite continuous tightening and `TIMING` prescribed a definite single take with no cut. Those instructions were not marked inside their sections as conservative inferred choices with unresolved mechanism/cuts.
- FAIL: enhanced `ACTION` included a non-occlusion prohibition that was also present in `CONSTRAINTS`; non-occlusion is owned only by `CONSTRAINTS`.
- PASS: no model-backed fusion, strict JSON validation, generation, rendered similarity, or production-quality result was claimed.

Round 7 is partial/FAIL and does not pass the reconstruction-evidence or exact-ownership behavior gates. Fixed-coverage interpolation must be omitted or qualified inside `CAMERA` and `TIMING`, and enhanced non-occlusion requirements must appear only in `CONSTRAINTS`. A new independent fresh-agent rerun must demonstrate both behaviors before Task 6 can pass.
