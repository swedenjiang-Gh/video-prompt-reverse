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
