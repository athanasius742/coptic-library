# PHASE 20 — Resolve cross-references, footnotes, TOC (stable IDs)
PRECONDITIONS: normalized content.xhtml; images already resolved (phase 30 ran).
RUN (deterministic, two-pass):
  python3 tools/resolve_refs.py <BOOK_DIR>
  Pass 1 collect: parse all chapters -> targets (headings, footnote bodies, TOC) and
    references (<a href="#..">, <sup><b><a href="#(n)">(n)</a></b></sup>, TOC links,
    prose "see chapter X").
  Pass 2 resolve (sequential by manifest.order):
    - assign stable IDs: ch-<NN>-<slug>, <slug>--sec-<n>, <slug>--fn-<n>, <slug>--fnref-<n>;
    - wire footnote<->backref in the st-takla markup (keep marker text verbatim;
      keep the <h6><a>الحواشي والمراجع</a></h6> + _____ block so renderer pairing works);
    - resolve #anchor / cross-chapter / inter-book refs against manifest.json/catalog.json;
    - DANGLING target -> downgrade <a> to <span> (keep text) + log dangling-ref. NEVER delete.
LLM: only to disambiguate fuzzy prose "see chapter X" to a chapter ID. Never invent a target.
SELF-CHECK: 0 new danglers; footnotes pair; IDs identical across two runs.
OUTPUT: rewritten content.xhtml; state.{anchor_registry,footnote_registry,heading_map};
        recompute source_hash.
