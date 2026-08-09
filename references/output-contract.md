# Prompt package output contract

`scripts/fuse_prompt_package.py` consumes the evidence manifest, four still-separated
observation streams, human project context, target engine settings, mode, and generation
time. It emits `prompt-package.json`; `prompt-package.md` is derived only after the JSON
passes `scripts/validate_prompt_package.py`.

The model-facing fusion uses four small contracts, not one full-package request. The base, I2V, and
enhanced stages represent prompts as eight named section objects containing attributed atom arrays.
The variant stage returns only camera-motion, lighting, and timing replacement atom arrays. The
controller copies fixed package fields, clones the seven unchanged base sections into each variant,
renders the final eight-line strings, and derives the attribution ledger before strict validation.

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
- `attribution`: exactly `status` and `entries`. `status` is `source-closed`; `entries` contains
  exactly one row per semicolon-delimited atom occurrence across the three main prompts and three
  variants. Each row records `fact_id`, exact `prompt_ref`, exact `atom`, owner section, source
  stream/reference/quote, evidence references, and status. Source-supported atoms contain an exact
  quote from the named input record. Conservative-inferred and creative atoms are labelled inside
  their owner section and carry no source record.

Every stage response and every Task 5 JSON/JSONL file boundary uses the strict parser. Each stage
rejects missing, null, or extra stage-owned fields before the next request. Duplicate keys,
`NaN`/infinities, Markdown fences, prefix/suffix prose, malformed JSON, invalid timestamps,
provenance loss, mismatches with requested metadata/engine, and missing, duplicate, extra,
mismatched, or unsupported attribution rows are rejected. Strict serialization uses
`allow_nan=False`. `PROMPT_PACKAGE_CONTRACT` remains the final controller/validator contract; it is
not sent back to each model stage as an oversized generation task.

## Privacy and invocation

One recursive gate runs before instruction construction, dry-run output, or runner invocation and
again on the fused package. It rejects semantic credential keys and common credential values,
including `github_pat_...`, plus absolute/private roots; harmless metadata such as `token_count`
is allowed. The llama.cpp adapter accepts only a loopback HTTP `llama-server`, posts exactly four
sequential JSON-object chat requests with no automatic retry, and returns only each assistant content
field. It does not use a shell or merge server logs into model content. An injected runner is used by
tests. Dry-run builds the common deterministic context and a redacted endpoint template without
process startup. The strict one-object parser still rejects commentary, Markdown fences,
prefix/suffix text, or multiple values inside assistant content.

## Markdown

`assets/prompt-package-template.md` is filled from validated JSON only. Evidence references reject
URI schemes, drive-like colons, controls, traversal, non-portable filename characters, and malformed
local path segments while accepting normal nested relative paths. Link targets are URL-encoded;
labels, headings, structural text, and list values are Markdown-escaped. Source media is never copied
into the package.
