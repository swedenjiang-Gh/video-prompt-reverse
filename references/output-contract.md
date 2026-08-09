# Prompt package output contract

`scripts/fuse_prompt_package.py` consumes the evidence manifest, four still-separated
observation streams, human project context, target engine settings, mode, and generation
time. It emits `prompt-package.json`; `prompt-package.md` is derived only after the JSON
passes `scripts/validate_prompt_package.py`.

## Strict JSON shape

The top-level object has exactly these fields:

- `metadata`: exactly `mode` and timezone-aware ISO 8601 `generated_at`.
- `media`: exactly `duration_seconds`, `width`, `height`, and `fps` copied from the evidence manifest.
- `shots`: ordered, non-overlapping, media-bounded records with exactly `id`, `timestamps`,
  `evidence_refs`, and `description`. IDs, timestamps, and portable relative evidence references
  must preserve the evidence manifest order and values.
- `sources`: exactly `skycaptioner`, `general_vlm`, `asr_ocr`, and `human_context`. Each value is
  a list of fusion-assigned references prefixed by its own namespace; the required lists must be
  copied exactly so provenance cannot be merged, moved, dropped, or invented.
- `five_role_review`: exactly `screenwriter`, `director`, `cinematographer`,
  `production_designer`, and `editor`, each with a non-empty review.
- `prompts`: complete `reconstruction_t2v`, `reconstruction_i2v`, and `enhanced` strings plus
  exactly three `single_variable_variants`. Every prompt is standalone and contains `SUBJECT`,
  `ACTION`, `SCENE`, `CAMERA`, `LIGHTING`, `TIMING`, `AUDIO`, and `CONSTRAINTS` sections. Each
  variant has exactly `changed_dimension` and `prompt`, and the three dimensions are unique.
- `engine`: exactly `name`, non-empty scalar `parameters`, and `compatibility_notes`. CLI-style
  engine flags are forbidden in prompt prose.
- `anchors`: a non-empty list of continuity anchors.
- `negative_constraints`: exactly separate `reconstruction_source` and `generation_stability`
  lists. Fidelity limits must not be collapsed into generation-stability negatives.
- `uncertainties`: a list of explicit uncertainties; it may be empty when none remain.

The model response must be one bare JSON object. Markdown fences, prefix/suffix prose, malformed
JSON, missing or extra fields, invalid timestamps, provenance loss, and mismatches with the
requested metadata/engine are rejected.

## Privacy and invocation

Raw secret-like keys or values, authorization material, absolute/private machine paths, and
parent-traversing evidence references are rejected recursively. The llama.cpp adapter passes an
argument list directly to `subprocess.run` with the prompt on stdin; it does not use a shell or
print the prompt, executable path, model path, stdout, or stderr. An injected runner is used by
tests. Dry-run builds the deterministic request and a redacted argument template without process
startup.

## Markdown

`assets/prompt-package-template.md` is filled from validated JSON only. Evidence is represented as
clickable relative Markdown links; source media is never copied into the package.
