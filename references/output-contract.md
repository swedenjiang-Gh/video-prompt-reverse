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
  exactly three `single_variable_variants`. Every prompt has exactly one ordered, non-empty line
  for `SUBJECT`, `ACTION`, `SCENE`, `CAMERA`, `LIGHTING`, `TIMING`, `AUDIO`, and `CONSTRAINTS`.
  Variant dimensions are restricted by the canonical dimension-to-section map; each complete
  variant must differ from `reconstruction_t2v` only in its declared section.
- `engine`: exactly `name`, non-empty finite scalar `parameters`, and `compatibility_notes`.
  CLI-style engine flags are forbidden in prompt prose.
- `anchors`: a non-empty list of continuity anchors.
- `negative_constraints`: exactly separate `reconstruction_source` and `generation_stability`
  lists. Fidelity limits must not be collapsed into generation-stability negatives, and the two
  lists must remain disjoint after Unicode, case, whitespace, and punctuation normalization.
- `uncertainties`: a list of explicit uncertainties; it may be empty when none remain.

The model response and every Task 5 JSON/JSONL file boundary use the same strict parser. Duplicate
keys, `NaN`/infinities, Markdown fences, prefix/suffix prose, malformed JSON, missing or extra
fields, invalid timestamps, provenance loss, and mismatches with the requested metadata/engine
are rejected. Strict serialization uses `allow_nan=False`.

The model-facing instruction embeds `PROMPT_PACKAGE_CONTRACT`, the same dependency-light canonical
contract from which validator field sets, source namespaces, roles, prompt sections, dimension
mapping, and variant count are derived. The contract also enumerates all binding leaf types and
cross-field invariants.

## Privacy and invocation

One recursive gate runs before instruction construction, dry-run output, or runner invocation and
again on the fused package. It rejects semantic credential keys and common credential values,
including `github_pat_...`, plus absolute/private roots; harmless metadata such as `token_count`
is allowed. The llama.cpp adapter writes the prompt to one UTF-8 temporary file and passes its path
through the verified `--file` argument in a structured argument list and removes the file in a
`finally` path. It does not use stdin for the initial chat prompt, a shell, or print the prompt,
executable path, model path, stdout, or stderr. An injected runner is used by tests. Dry-run builds
the deterministic request and a redacted argument template without process startup. The strict
one-object parser intentionally rejects any CLI banner, prompt echo, Markdown fence, or exit marker.

## Markdown

`assets/prompt-package-template.md` is filled from validated JSON only. Evidence references reject
URI schemes, drive-like colons, controls, traversal, non-portable filename characters, and malformed
local path segments while accepting normal nested relative paths. Link targets are URL-encoded;
labels, headings, structural text, and list values are Markdown-escaped. Source media is never copied
into the package.
