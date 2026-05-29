# PHASE 40 — Metadata (validate meta.json; fill genuine gaps; merge-not-clobber)
ROLE: validate meta.json against the schema (code), and fill GENUINE gaps with the LLM,
  merging — never clobbering — existing human values.
PRECONDITIONS: meta.json present (phase 00 asserted it); chapters resolved enough to read
  titles/topics from.
RUN (deterministic): python3 tools/state.py ... / the metadata step
  - VALIDATE meta.json against the BookMeta shape (prompts/lib/directory-layout.md §0.3):
    slug, title, author, author_slug, source, source_url, epub, cover, language ("ar"|"en").
LLM (judgment, schema-validated, merge-not-clobber): fill ONLY genuinely empty fields:
  - title_en, author_en, description_en (English renderings/fallbacks);
  - topics, keywords (from chapter content);
  - series / series_en (if the book is part of a series).
  Do NOT overwrite any non-empty existing value (human edits are authoritative). *_en fields
  are optional with Arabic fallback (bookDisplay); leave blank rather than guess wrongly.
SELF-CHECK: meta.json still validates; no existing human value was changed; re-run is a no-op.
ON FAILURE: schema-invalid meta.json after the step -> log state.issues and STOP.
OUTPUT: books/.../meta.json (merged); state.phases.metadata=done (+input_hash).
