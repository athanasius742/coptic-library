# PHASE 60 — Verification & quality gates (all must pass)
RUN (deterministic): python3 tools/verify_book.py <BOOK_DIR>
  1. schemas valid (meta/manifest/state); spine==manifest==disk; chapter_links_guess==#chapters.
  2. image-ref integrity (referenced==present; every <img> has alt).
  3. link integrity: 0 dangling #anchors / cross-file refs.
  4. round-trip text diff WITH tashkeel within tolerance for every chapter.
  5. EPUB validation (lxml always; epubcheck 0 ERROR/FATAL if available).
  6. catalog consistency; status still "draft".
  7. author: meta.author_slug==catalog.author_slug; info.json exists or needs_review logged.
  8. Arabic/RTL checklist (prompts/lib/arabic-rtl.md).
LLM: triage any failure into auto-fixable (re-run prior phase) vs human-flag.
ON ANY HARD FAILURE OR STOP CONDITION: write REPORT.md, set review:"pending", STOP.
OUTPUT: state.issues + per-check results; pass -> proceed to phase 90.
