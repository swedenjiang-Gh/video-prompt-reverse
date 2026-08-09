# Prompt analysis dimensions

Use this checklist per shot and across the full sequence. Anchor every statement to timestamped evidence or a named source stream; mark inference and uncertainty instead of filling gaps.

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
| `ACTION` | Behavior only. |
| `SCENE` | Environment and props only. |
| `CAMERA` | Framing, lens, and camera motion only. |
| `LIGHTING` | Illumination and color only. |
| `TIMING` | Duration, pacing, and cuts only. Never restate specific actions, camera paths, or lighting changes. |
| `AUDIO` | Sound only. |
| `CONSTRAINTS` | Invariants and negatives only. Never prescribe a changed dimension. |

Before cloning single-variable variants, rewrite `reconstruction_t2v` to remove every cross-section duplicate. Then copy all seven unchanged sections in full and change only the mapped section.

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
- Keep SkyCaptioner structural observations, general VLM observations, ASR/OCR, and human context individually attributable until fusion.
- Preserve contradictions. State which source supports each alternative and what evidence would resolve it.
- Use explicit uncertainty for occluded identity, unreadable text, inaudible speech, ambiguous lens choice, hidden action, or unsupported physics.
- Describe only observable source fidelity in reconstruction prompts. Put intentional creative changes in the enhanced prompt or a declared single-variable variant.
