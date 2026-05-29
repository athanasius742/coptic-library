# PHASE 00 — Preflight / triage (detect inputs + tools; init state; route Phase1 vs Phase2)
ROLE: assert preconditions, detect the environment, decide phase ("html" vs "pdf"), and
  initialize/load .build/state.json. Owner: CODE. The LLM does NOTHING here except read the
  reported result. NEVER guess paths; STOP precisely on any missing precondition.
PRECONDITIONS: BOOK_DIR (arg) is absolute, under books/st-takla.org/<author-slug>/<book-slug>/.
RUN (deterministic, no network): python3 tools/preflight.py <BOOK_DIR>
  - ASSERT Phase-1 inputs exist: meta.json, manifest.json, and chapters/<NN-slug>/content.xhtml
    (OR pages/*.html + <slug>.epub from which they can be (re)built); note cover.jpg/images/.
    If chapters/*/content.xhtml are absent but pages/* + .epub exist, flag "rebuild needed"
    (extract_book.py path) rather than failing.
  - DETECT tools (§0.8): magick, ebook-convert, java, python3, beautifulsoup4, lxml (expect
    present); rapidfuzz (needed for phase 45 — flag if absent); epubcheck.jar (optional);
    pandoc/ebooklib (ABSENT — never depend on them). Record availability in state.
  - DETERMINE phase: if the input is an existing book dir -> phase="html". If the input is a
    PDF -> phase="pdf" and ROUTE to phases/05-pdf-intake.md (continue at phase 20 after it).
  - INIT/LOAD .build/state.json via the tools/state.py helpers: create if absent
    (book_id, schema_version:1, phase, empty phases map), else load existing (resume).
  - COMPUTE source_hash (sha256 over manifest.json + every content.xhtml) and store it for
    hash-gating; mark per-phase status pending/stale where inputs changed.
OWNER: CODE (assertions, tool detection, hashing, state init). LLM: none.
SELF-CHECK: state.json validates against prompts/lib/schemas/state.schema.json; phase is set;
  source_hash present; re-run is a no-op when inputs are unchanged.
ON FAILURE / STOP: any missing precondition (no meta.json / manifest.json / chapters or
  pages+epub) -> STOP with a precise message naming the missing path. Do NOT guess.
OUTPUT: .build/state.json (created/loaded) with phase, source_hash, tool availability,
  per-phase status. NEXT: phase 10 (html) — or phase 05 then phase 20 (pdf).
