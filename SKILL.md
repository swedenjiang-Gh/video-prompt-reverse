---
name: video-prompt-reverse
description: Use when an authorized local or public-reference video needs prompt reverse-engineering, T2V/I2V reconstruction, video-prompt diagnosis, similar-video prompt generation, or adaptation for a target video engine.
---

# Video Prompt Reverse

## Core rule

Enter through `media-studio-orchestrator`. Own reverse-prompt analysis only. Delegate evidence extraction to `video-learning` and approved optional local generation to `comfyui-video-workflow-author`.

Never submit a local or cloud generation task silently.

## Workflow

1. Confirm authorization and source class. Stop if access requires bypassing controls.
2. Ask `video-learning` to produce media facts and an event-driven evidence manifest. Use entry, peak, and exit evidence for every event interval.
3. If no usable event intervals exist, declare a fixed-interval fallback before extraction and carry it into uncertainties. Treat frames as sampled states, not continuous-motion proof.
4. Run the SkyCaptioner structural pass. Keep visual-only observations and raw responses auditable.
5. Assemble `skycaptioner`, `general_vlm`, `asr_ocr`, and `human_context` separately. Preserve empty streams; never move observations across namespaces.
6. Fuse with the existing 32B interface. Produce the five-role review, T2V/I2V reconstructions, enhanced prompt, and three complete single-variable variants.
7. Validate strictly against the manifest, required sources, metadata, and target engine. Fix rejected data at its source.
8. Deliver validated JSON and its derived Markdown. Keep source-fidelity and generation-stability negatives separate; retain uncertainties.
9. Offer the user a generation route: MiniMax H3, Wan/local, Seedance/cloud, another engine, or no generation. Treat local-versus-cloud and H3-versus-Wan as user choices.

Print every single-variable variant as a complete standalone prompt with all eight canonical sections in order. Copy the seven unchanged sections in full from `reconstruction_t2v`; change exactly the section mapped by `changed_dimension`. Never deliver a replacement line, ellipsis, baseline reference, `same as above`, or `other sections unchanged` shorthand.

Before producing variants, localize each variable's semantics in `reconstruction_t2v` to its mapped section. Keep the other seven sections semantically compatible with both the baseline and the changed section. A variant is invalid if an unchanged section still requires the old camera, lighting, timing, or action behavior; repair the baseline section boundaries before emitting variants.

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
