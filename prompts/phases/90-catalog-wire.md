# PHASE 90 — Catalog wiring (upsert tools/catalog.json as draft; regenerate views)
ROLE: upsert the tools/catalog.json entry (keyed by book_id) at status:"draft" (NOT verified),
  then regenerate the markdown catalogs. Owner: CODE. NEVER write status:"verified" here —
  that is the phase 99 human gate.
PRECONDITIONS: phase 60 (verify) passed; meta.json + manifest.json valid; author_slug set
  (phase 45); content chapters counted from chapters/ on disk.
RUN (deterministic, atomic): python3 tools/catalog_upsert.py <BOOK_DIR> --status draft
  - upsert the entry keyed by book_id (keep the flat-list catalog shape); set:
    dest, author_slug, book_slug, section ("arabic"|"english" from meta.language),
    chapter_links_guess = CONTENT-CHAPTER COUNT (== len(chapters/) == non-index manifest
    length — this is the UI count source, §0.2), and status:"draft".
  - status:"draft" keeps the book INVISIBLE to the web app (catalog.ts filters "verified").
THEN regenerate the markdown catalogs (docs only; web ignores them):
  python3 tools/make_views.py
SELF-CHECK: catalog entry exists keyed by book_id; chapter_links_guess == content-chapter
  count; status is "draft" (NOT "verified"); re-run is a no-op (idempotent upsert).
ON FAILURE: log to state.issues and STOP.
OUTPUT: tools/catalog.json (entry, status:"draft"), regenerated root markdown catalogs;
  state.phases.catalog=done. NEXT: phase 99 (report + human gate).
