# PHASE 99 — Report + human review gate -> flip to verified
ROLE: write the per-book REPORT.md, set review:"pending", and STOP for a human. Only after
  human approval does status flip to "verified". Owner: CODE writes the report; the HUMAN
  approves; a tiny tool performs the flip. Automation NEVER flips "verified" on its own.
PRECONDITIONS: phases 00..90 done; catalog entry at status:"draft"; all phase 60 gates passed.
RUN (deterministic): write books/.../REPORT.md and set state.review:"pending"
  REPORT.md MUST contain:
  - counts: chapters, images (present/missing), footnotes resolved, dangling refs downgraded;
  - issues: the full state.issues review queue (severity/code/detail/chapter);
  - sample chapter links (a few content.xhtml / internal routes to spot-check);
  - AUTHOR resolution summary (slug, method, confidence, needs_review);
  - SOURCE RE-ATTRIBUTION (§4.1a): list EVERY rewrite {chapter, before, after} for human
    approval, PLUS every pending_review self-reference for the human to resolve (rewrite/keep).
    These alter authored/sacred text and MUST be human-approved before verified.
HUMAN REVIEW GATE (mandatory): a human reviews REPORT.md. Until approval the book is INVISIBLE
  to the web app (status:"draft").
ON APPROVAL: python3 tools/publish.py <BOOK_DIR> --approve
  - flips tools/catalog.json.status -> "verified" AND state.review -> "approved".
  - run tools/make_views.py if the markdown catalogs need regenerating.
STOP CONDITIONS (halt, leave status:"draft"): any unresolved §4.1a rewrite/pending_review not
  yet human-approved; any open error-severity issue; missing precondition. NEVER auto-verify.
OUTPUT: books/.../REPORT.md; state.review:"pending" (then "approved" post-flip);
  tools/catalog.json.status -> "verified" ONLY after --approve.
