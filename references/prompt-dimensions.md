# Prompt analysis dimensions

Use this checklist per shot and across the full sequence. Anchor every statement to timestamped evidence or a named source stream; mark inference and uncertainty instead of filling gaps.

## Source closure

Use a two-pass source-closure recipe:

1. **Source draft:** Draft all six complete prompts from facts explicitly present in `skycaptioner`, `general_vlm`, `asr_ocr`, or `human_context`, plus owner-local `conservative inferred choice` or `creative choice` atoms. Do not claim closure yet.
2. **Final atomization:** Freeze the final prompt wording. Separate atomic occurrences with semicolons and build the `attribution.entries` inventory from the final text: `fact_id | prompt_ref | atom | owner section | source stream | source_ref | source_quote | evidence_refs | status`.

Atoms include every identity, attribute, adjective, color, count, direction, location, action phase, gaze path, expression, pose, focus property, light color, pacing, duration, and edit declaration. One row covers one atom occurrence only; never hide multiple details in a composite row. Every final prompt atom maps to exactly one row, and every row maps back to exactly one prompt occurrence.

For each `source-supported` row, the atom contains an exact `source_quote` from its named source record plus matching evidence references. For each inferred or creative row, `source stream` is `none` and the same status appears inside the owner section. Reviews, anchors, summaries, and inventory references alone cannot replace the named-stream text.

Claim `source-closed` only after both directions pass. Otherwise list unmatched or invalid atoms and report `attribution incomplete` and `partial`.

Treat every detail as its own fact. A broad observation such as `bedroom scene` does not source earrings, necklaces, garments, prop state, layout, pose, depth of field, or illumination. Enumerate each supported detail with evidence references or omit it.

Declare the actual authorized I2V image before `reconstruction_i2v`: `I2V input asset: <portable evidence or input-asset path>; role: first-frame|reference; authorization: approved`. If no approved image exists, write `I2V input asset: no approved reference image supplied`, make the I2V prompt conditional, and make no input-lock claim.

## Analysis and reconstruction checklist

| Dimension | Inspect and preserve |
|---|---|
| Narrative, action, and physics | Beat purpose, action phases, cause/effect, timing, contact, weight, inertia, deformation, and environmental response. |
| Subject, blocking, and identity | Stable identity cues, wardrobe/props, pose, gaze, screen position, entrances/exits, spacing, and occlusion. |
| Shot size and type | Extreme close-up through extreme wide, insert/establishing/POV/over-the-shoulder, and any transition between sizes. |
| Angle and camera position | Eye/high/low/Dutch/overhead angle, camera height, side, distance, orientation, and subject relationship. |
| Lens and depth | Perspective compression or expansion, apparent focal character, depth of field, focus plane, rack focus, foreground/midground/background separation. |
| Camera motion | Locked, pan, tilt, roll, dolly, truck, pedestal, orbit, crane, handheld, zoom, speed, path, start/stop, and stabilization character. |
| Lighting and image character | Key/fill/rim direction and quality, exposure, contrast, time of day, tone, palette, saturation, grain, sharpness, and surface texture. |
| Environment and production design | Location, architecture, set dressing, weather, atmosphere, practicals, props, materials, scale, and spatial continuity. |
| Editing rhythm and continuity | Shot order, duration, cut type, match, screen direction, eyeline, action continuity, tempo, and transition logic. |
| Audio and dialogue | Spoken content, speaker, language, delivery, music, ambience, effects, synchronization, and silence. Attribute ASR/OCR separately from visual observation. |
| Negative constraints | Source-fidelity exclusions derived from the reference, kept separate from artifact-prevention or generation-stability constraints. |

## Canonical prompt section ownership

Make the canonical sections orthogonal before producing variants:

| Section | Owns |
|---|---|
| `SUBJECT` | Identity and appearance only. |
| `ACTION` | Affirmative event emergence, behavior, interactions, state changes, and reactions only. Refer to an already named prop by its neutral entity name; do not repeat its attributes, state, or location. |
| `SCENE` | Static environment, prop attributes, and layout only. Use noun/location statements such as `an open tan book between the subjects`; `held`, `holding`, `being held`, and other interactions belong to `ACTION`. A lamp or cabinet may be named as a prop, but not as lit, glowing, changing, or in an illumination state. A book or page may be named as a prop, but its text legibility is not a scene property. |
| `CAMERA` | Framing, lens, camera motion, focus, depth of field, and bokeh only, including epistemic uncertainty or prohibitions about those properties. Never mention cuts, editing, transitions, shot count, or single-take structure. |
| `LIGHTING` | Emitted light, color, exposure, and shadow only. Never mention bokeh, defocus, focus, or lens. |
| `TIMING` | Duration, pacing, shot count, cuts, editing, transitions, and single-take structure only, including epistemic uncertainty or prohibitions about those properties. Own both positive and negative declarations such as no cuts. Never restate specific actions, camera paths, or lighting changes. |
| `AUDIO` | Sound and audiovisual synchronization only. Reconstruction audio contains resolved source evidence or an explicit unresolved boundary, never invented source-fidelity sound. |
| `CONSTRAINTS` | A genuine invariant or negative not already stated in another section, including readable/visible-text prohibitions and non-occlusion requirements. Camera mechanism/lens/focus uncertainty stays in `CAMERA`; shot-count/single-take/no-cut/cut/transition uncertainty stays in `TIMING`. Never restate subject attributes, action, scene layout, camera, lighting, or timing semantics. |

Before delivery, audit every clause in every complete prompt: `reconstruction_t2v`, `reconstruction_i2v`, `enhanced`, and each variant. Build enhanced events with emergence and reactions in `ACTION`, unchanged static set and props in `SCENE`, emitted illumination in `LIGHTING`, and duration, pacing, cuts, or transitions in `TIMING`. A clause belongs to exactly one owner section in each prompt.

Entity names may repeat as grammatical references; semantic payload may not. Put each identity/appearance attribute in `SUBJECT`, each prop attribute or static location in `SCENE`, and each interaction in `ACTION`. After a book is defined in `SCENE`, `ACTION` uses only `the book`. `CONSTRAINTS` adds only an invariant or negative not already owned elsewhere.

Before cloning single-variable variants, apply the same audit to `reconstruction_t2v`. If changing another dimension could make a clause false, move it to that dimension's section. Rewrite the baseline until this lint passes; then copy all seven unchanged sections in full and change only the mapped section.

For reconstruction audio, write only resolved evidence. If the source audio remains unresolved, use an action-independent boundary such as `source audio unresolved; no verified dialogue, music, ambience, or synchronized effects`. Keep that boundary unchanged in an `ACTION`-only variant. An action plus its synchronized sound is a two-section creative change, not a single-variable action variant.

For fixed-interval coverage or empty event intervals, reconstruction `CAMERA` may state observed endpoint framing and `TIMING` may state supported duration or pacing. An interpolated generation bridge must identify itself inside its owner: `conservative inferred reconstruction choice; exact camera mechanism unresolved` in `CAMERA`, and `conservative inferred reconstruction choice; cuts/transitions unresolved` in `TIMING`. Otherwise omit continuous-motion and no-cut claims. Keep these epistemic clauses out of `CONSTRAINTS`; before cloning, make all seven unchanged sections neutral toward a replacement `CAMERA` or `TIMING` choice. A separate uncertainty list cannot qualify an unlabelled prompt instruction.

Fixed frames support sampled `ACTION` poses or states, not a connecting action path. A gaze alternation, maintained behavior, response, or other transition must say inside `ACTION`: `conservative inferred reconstruction choice; exact action path unresolved`. A pacing choice that connects samples receives the same conservative label inside `TIMING`.

Apply ownership to prohibitions as strictly as positive descriptions: move a no-cut clause from `CAMERA` to `TIMING`, and move a no-readable-text clause from `SCENE` to `CONSTRAINTS`. Delete the source copy after each move; compatible duplication still fails the lint.

Build enhanced `ACTION` from affirmative event changes and reactions. Move non-occlusion wording such as `does not obscure the face or hands` to `CONSTRAINTS`, then delete it from `ACTION` so the prohibition has one owner.

Before cloning a `LIGHTING` variant, make `SCENE` and `CONSTRAINTS` illumination-neutral. Words such as `warm`, `cool`, `night`, `day`, `bright`, and `dim` belong only in `LIGHTING`, not in environment, layout, continuity, or invariant clauses.

For text-related top-level negatives, `reconstruction_source` prohibits invented specific verifiable body text, titles, or illustrations. `generation_stability` prohibits malformed pseudo-glyphs, glyph flicker, or page-text texture instability. Do not repeat readable/unreadable source fidelity in the stability list.

## Five-role anchors

- **Screenwriter:** identify the beat, intention, causal action, information revealed, and dialogue function.
- **Director:** define performance, blocking, staging, emotional progression, and audience attention.
- **Cinematographer:** define shot geometry, lens/depth, camera motion, lighting, exposure, palette, and texture.
- **Production designer:** define environment, props, wardrobe, materials, practical sources, and continuity anchors.
- **Editor:** define shot order, usable action boundaries, duration, rhythm, transitions, audiovisual synchronization, and continuity risks.

Write each role's review as a concrete contribution to reconstruction, not a restatement of the same caption.

## Evidence discipline

- Prefer corroboration across entry/peak/exit frames or adjacent shots for motion and continuity claims.
- Treat a fixed-interval fallback as lower-confidence temporal coverage and declare it.
- Keep SkyCaptioner structural observations, general VLM observations, ASR/OCR, and human context individually attributable until fusion. Label current controller/agent frame inspection as `controller/general-VLM observation` in `general_vlm`. Use `human_context` only when an explicitly identified human record supplied the fact; do not relabel agent/model observation as human.
- Admit a prompt atom only through the final two-pass inventory bijection. Every source-supported atom points to explicit equivalent named-stream text and evidence references; every owner-local conservative/creative atom has `source stream: none`; otherwise omit it or report attribution incomplete.
- Preserve contradictions. State which source supports each alternative and what evidence would resolve it.
- Use explicit uncertainty for occluded identity, unreadable text, inaudible speech, ambiguous lens choice, hidden action, or unsupported physics.
- Describe only observable source fidelity in reconstruction prompts. Put intentional creative changes in the enhanced prompt or a declared single-variable variant.
