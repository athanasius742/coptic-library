# PHASE 10 — Normalize chapter HTML to the renderer subset
PRECONDITIONS: .build/state.json exists (phase "html"); chapters/*/content.xhtml present.
GOAL: every content.xhtml conforms to prompts/lib/html-subset.md (Appendix D).
RUN (deterministic, no network):
  python3 tools/normalize_chapters.py <BOOK_DIR>
  - extract inner <body>; unwrap font/center/div; drop tags/attrs to the allowlist;
    ensure ONE top-level <h1> title; keep dir/lang on roots; ensure images are images/<file>.
LLM (ONLY if needed, each diff-gated):
  - ambiguous heading hierarchy (h1/h3/h6 soup) -> propose sane h2.. levels;
  - mojibake/CP1256 remnants -> repair. After any LLM edit, run the round-trip tashkeel
    diff; if delta > tolerance, DISCARD the edit, keep deterministic text, log issue, STOP.
SELF-CHECK: re-run is a no-op; sanitize-subset validator passes; diff ≈ 0.
ON FAILURE: log to state.issues and STOP.
OUTPUT: rewritten chapters/*/content.xhtml; state.phases.normalize=done (+input_hash).
