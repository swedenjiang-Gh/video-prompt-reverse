---
name: video-prompt-reverse
description: Use when an authorized local or public-reference video needs prompt reverse-engineering, T2V/I2V reconstruction, video-prompt diagnosis, similar-video prompt generation, or adaptation for a target video engine.
---

# Video Prompt Reverse

## Core rule

Enter through `media-studio-orchestrator`. Own reverse-prompt analysis only. Delegate evidence extraction to `video-learning` and approved optional local generation to `comfyui-video-workflow-author`.

Never submit a local or cloud generation task silently.

## Output ownership

If prompt reverse is one stage of a short-drama or video-production project, keep its evidence, structured records, prompt package, comparison outputs, and acceptance notes in that project. Otherwise create one self-contained job under `VIDEO_PROMPT_REVERSE_ROOT\<job>\` (default `D:\MediaStudio\VideoPromptReverse\<job>\`). Optional H3/Wan generation is only an execution step: move the resulting comparison media into the owning reverse job or project instead of classifying it as a standalone ComfyUI deliverable. Do not copy a source download into the job; reference its centralized path.

## Workflow

1. Confirm authorization and source class. Stop if access requires bypassing controls.
2. Ask `video-learning` to produce media facts and an event-driven evidence manifest. Use entry, peak, and exit evidence for every event interval.
3. If no usable event intervals exist, declare a fixed-interval fallback before extraction and carry it into uncertainties. Treat frames as sampled states, not continuous-motion proof.
4. Run the SkyCaptioner structural pass. Keep visual-only observations and raw responses auditable.
5. Assemble `skycaptioner`, `general_vlm`, `asr_ocr`, and `human_context` separately. Preserve empty streams; never move observations across namespaces. Label frame observations made by the current controller or agent as `controller/general-VLM observations` in `general_vlm`. Use `human_context` only for an explicitly identified human record, such as user-provided authorization or story context; never call an agent/model observation human. Before a visual identity, accessory, garment, prop attribute, pose, or state enters a prompt, record it in one named source stream with an evidence reference; otherwise omit it.
6. Run the five-role reconstruction review: **screenwriter** (beat, intention, causal action, information, dialogue function), **director** (performance, blocking, staging, emotional progression, audience attention), **cinematographer** (shot geometry, lens/depth, camera motion, lighting, exposure, palette, texture), **production designer** (environment, props, wardrobe, materials, practical sources, continuity), and **editor** (shot order, action boundaries, duration, rhythm, transitions, audiovisual synchronization, continuity risks). Each role must contribute a concrete reconstruction decision, not repeat the same caption.
7. Fuse through four bounded local `llama-server` HTTP stages: base T2V plus five-role review, I2V, enhanced, then three changed variant sections. Run each stage once with no automatic retry. Let the controller copy manifest metadata, media, shots, source references, and target-engine fields; expand every variant from the base prompt; then derive the final atom-attribution ledger.
8. Validate strictly against the manifest, required sources, metadata, and target engine. Fix rejected data at its source.
9. Deliver validated JSON and its derived Markdown. Keep source-fidelity and generation-stability negatives separate; retain uncertainties.
10. End every delivery with an explicit five-option offer: MiniMax H3, Wan/local, Seedance/cloud, another engine, or no generation. Do not merely say the user must choose, and never execute an option without the user's selection. Treat local-versus-cloud and H3-versus-Wan as user choices.

Close prompt attribution in two passes. First, draft the base T2V, I2V, enhanced prompt, and only the three variant replacement sections from explicit facts in the four source streams plus owner-local conservative or creative choices; do not call the draft source-closed yet. The controller copies the seven unchanged base sections into each variant. Second, freeze all six resulting complete prompts, split every clause into atomic occurrences, and build the inventory from those final atoms: `fact_id | prompt_ref | normalized atom | owner section | source stream | evidence_refs | status`.

Represent the three main fusion drafts as eight named section objects containing prompt-atom arrays. The variant stage returns only `camera_motion`, `lighting`, and `timing` replacement atom arrays. The controller joins atom text with semicolons and derives one `attribution.entries` row for each final occurrence, so the model never controls final line formatting, copied sections, fixed package fields, or row coverage. Reject missing, null, or extra stage fields immediately; do not fall back to the earlier one-shot full-package request. A `source-supported` atom must include an exact `source_quote` copied from its named source record plus that record's `source_ref` and matching evidence references. A `conservative-inferred` or `creative` atom must carry its label inside the owning prompt section and use no source record. Let the shipped validator establish the two-way mapping; prose assertions alone never establish closure.

Canonicalize model atoms before final rendering. Accept the legacy alias `supported` only when its exact quote, namespaced source record, and evidence references all close; otherwise downgrade it to an owner-local `conservative-inferred` atom and remove the invalid source claim. Normalize creative atoms to null source fields and an explicit label. If a variant repeats its baseline section, synthesize one declared owner-local change for that dimension rather than retrying the model. If I2V merely copies T2V, add the approved task-local first-frame path and binding role, or explicitly state that no approved frame exists. Replace implementation-oriented negative constraints with source-fidelity and generation-stability prohibitions.

Atomic occurrences include every identity, attribute, adjective, color, count, direction, location, action phase, gaze path, expression, pose, focus property, light color, pacing, duration, and edit declaration. One row represents one atom occurrence; a combined row cannot cover several details. Every final prompt atom has exactly one inventory row, and every inventory row points to exactly one final prompt occurrence. Repeated entity names are grammatical references, but every factual predicate still participates in this bijection.

For each `source-supported` row, the normalized atom must already appear explicitly, verbatim or equivalently, in `skycaptioner`, `general_vlm`, `asr_ocr`, or `human_context`, with evidence references. Each inferred or creative row uses `source stream: none` and repeats its status inside the owner section. Five-role notes, anchors, and summaries are downstream interpretations, not source streams, and cannot close a missing atom.

After both directions pass, the result may say `source-closed`. If any prompt atom lacks a row, any row bundles multiple atoms, any source-supported atom is absent from its named stream, or any inferred/creative atom lacks its owner-local label, report `attribution incomplete` and `partial`; never claim source closure.

Do not let a broad source summary license unlisted detail. Hair, identity, earrings, necklaces, garments, prop state, layout, pose, depth of field, illumination, and every other prompt detail must each be explicit in the named stream or explicitly marked as a conservative/creative choice in its owner section.

Before `reconstruction_i2v`, print `I2V input asset: <portable evidence or input-asset path>; role: first-frame|reference; authorization: approved`. The path must identify the actual authorized image selected for I2V. If none was supplied and approved, print `I2V input asset: no approved reference image supplied`, keep the I2V prompt conditional, and do not claim that identity, framing, or appearance is locked to an input image.

Print every single-variable variant as a complete standalone prompt with all eight canonical sections in order. Copy the seven unchanged sections in full from `reconstruction_t2v`; change exactly the section mapped by `changed_dimension`. Never deliver a replacement line, ellipsis, baseline reference, `same as above`, or `other sections unchanged` shorthand.

Before writing any complete prompt, read [canonical prompt section ownership](references/prompt-dimensions.md#canonical-prompt-section-ownership). Lint every clause in `reconstruction_t2v`, `reconstruction_i2v`, `enhanced`, and each variant. Put affirmative event emergence, state changes, interactions, and reactions in `ACTION`; static environment and props in `SCENE`; emitted illumination, exposure, and shadows in `LIGHTING`; and only duration, pacing, cuts, edits, and transitions in `TIMING`. Write `SCENE` as a static noun/location statement such as `an open book between the subjects`; `held`, `holding`, `being held`, and other interactions belong only in `ACTION`.

Before cloning variants, rewrite `reconstruction_t2v` until every clause has exactly one owner. If changing another dimension could make a clause false, move it to that dimension's section. Reject a variant if any unchanged section restates or requires the changed action, camera, lighting, or timing.

Entity names may recur across sections as grammatical references, but each attribute, state, location, or action meaning has one owner. `SCENE` owns prop attributes and static layout, for example `an open tan book between the subjects`; `ACTION` then says only how a subject interacts with `the book`, without repeating its color, open/closed state, or location. `CONSTRAINTS` contains only a genuine invariant or negative not already stated in `SUBJECT`, `ACTION`, `SCENE`, `CAMERA`, `LIGHTING`, or `TIMING`.

Build reconstruction `AUDIO` only from resolved audio evidence. When source audio is unresolved, keep it unresolved with an action-independent boundary such as `source audio unresolved; no verified dialogue, music, ambience, or synchronized effects`. Clone that boundary unchanged into variants. If an action change also needs a synchronized sound, classify it as an `AUDIO` change or a separate creative prompt, not an `ACTION`-only variant.

When reconstruction uses fixed-interval frames or empty event intervals, write only observed endpoint framing in `CAMERA` and supported duration or pacing in `TIMING`. If generation needs an interpolated bridge, label it inside the owning section: `conservative inferred reconstruction choice; exact camera mechanism unresolved` in `CAMERA`, and `conservative inferred reconstruction choice; cuts/transitions unresolved` in `TIMING`. An external uncertainty list does not turn an unlabelled continuous move or no-cut instruction into source evidence.

Under the same fixed-frame boundary, `ACTION` may state sampled poses or states only. Label any connecting change such as gaze alternation, sustained behavior, or response inside `ACTION` as `conservative inferred reconstruction choice; exact action path unresolved`. Label a pacing choice that connects samples inside `TIMING` as conservative too.

Keep epistemic clauses owner-local. Put camera mechanism, lens, focus, or camera-motion uncertainty and prohibitions in `CAMERA`; put shot-count, single-take, no-cut, cut, transition, or editing uncertainty and prohibitions in `TIMING`. Delete these clauses from `CONSTRAINTS` before cloning variants so every unchanged section remains neutral toward a changed `CAMERA` or `TIMING` choice.

Put every cut, edit, transition, shot-count, or single-take clause—including a prohibition such as no cuts—only in `TIMING`, never in `CAMERA`. Put every readable-text prohibition only in `CONSTRAINTS`, never in `SCENE`; `SCENE` may name a book or page as a prop without assigning its text a legibility rule. Remove the original clause after moving it so no ownership duplicate remains.

Keep the seven unchanged sections neutral for a `LIGHTING` variant. Remove `warm`, `cool`, `night`, `day`, `bright`, `dim`, and other illumination or tone states from `SCENE` and `CONSTRAINTS`; put them only in `LIGHTING`.

Keep top-level negative categories semantically separate. For text-related entries, `reconstruction_source` prohibits inventing specific verifiable body text, titles, or illustrations; `generation_stability` addresses malformed pseudo-glyphs, glyph flicker, or page-text texture instability without repeating a readable/unreadable-text fidelity rule.

Write enhanced `ACTION` as affirmative event behavior. Put every non-occlusion requirement, including not obscuring eyes, faces, or hands, only in `CONSTRAINTS`; remove it from `ACTION`.

Use the shipped scripts for deterministic work; inspect their interfaces instead of reproducing code, schemas, or commands here.

## Evidence and proof boundaries

- Attribute claims to the manifest or one of the four streams. Mark inferred, conflicting, or unsupported details uncertain.
- Distinguish static health (files and executable structure), executable smoke (a component starts), visual similarity (a rendered comparison), and production quality (human acceptance across outputs). Never promote one level as proof of another.
- Keep credentials, private roots, source media, and outputs out of public Skill files.

## Load references only when needed

- Read [runtime-setup.md](references/runtime-setup.md) before checking or preparing the local SkyCaptioner/Qwen/llama.cpp runtime.
- Read [prompt-dimensions.md](references/prompt-dimensions.md) when analyzing evidence, writing the five-role review, or reconstructing prompts.
- Read [output-contract.md](references/output-contract.md) when constructing, diagnosing, or validating a prompt package.
- Read [engine-adapters.md](references/engine-adapters.md) only after an engine is requested or the user asks for generation choices.
- Read [acceptance.md](references/acceptance.md) when reporting validation status or proof limits.
- Read [upstream-and-sources.md](references/upstream-and-sources.md) when auditing attribution or adapting cited prompt examples.

## Common failures

| Failure | Correction |
|---|---|
| One blended caption becomes the evidence record | Restore four separate streams before fusion. |
| A representative frame is described as motion | Restrict the claim to visible state or corroborate it across timestamps. |
| Enhanced or variant outputs are missing | Rebuild the complete package and revalidate. |
| All negatives are merged | Separate source-reconstruction fidelity from generation stability. |
| Engine flags appear in prose | Put verified settings in structured parameters. |
| Runnable is called production-ready | Report the actual proof level. |
