# PHASE 15 — Re-attribute st-takla self-references (external, 3rd-person)
ROLE: rewrite ONLY st-takla editorial self-promotion asides (first-person "we / our site"
  voice that implies the reader is on st-takla) into NEUTRAL THIRD-PERSON attribution to
  st-takla as a SEPARATE, EXTERNAL website. This is THE sanctioned exception to the
  verbatim/round-trip rule (§2): a surgical, span-bounded edit, change-logged.
PRECONDITIONS: normalized content.xhtml (phase 10 done); runs BEFORE phase 20 (no anchors yet).
INPUTS: chapters/<NN-slug>/content.xhtml.  OUTPUTS: rewritten matched spans only;
  state.source_reattribution{count, rewrites[], pending_review[]}.
PROCEDURE:
  1. DETERMINISTIC SCAN (code, tools/reattribute_source.py): flag spans containing st-takla
     markers — موقع الأنبا تكلا / الأنبا تكلاهيمانوت / موقعنا / st-takla / St-Takla.org —
     COMBINED WITH first-person/"our-site" framing — تكلمنا / ذكرنا / نشرنا / على موقعنا /
     في موقعنا. Emit a candidate list with surrounding context.
  2. LLM MINIMAL REWRITE (judgment): for each candidate, rewrite ONLY the flagged span into
     neutral 3rd-person external attribution (st-takla as another site, optionally add
     "(st-takla.org)"), preserving the author's meaning and the rest of the sentence.
     Do NOT touch anything outside the span.
  3. CHANGE LOG (replaces the round-trip diff here): record {chapter, before, after, reason}
     for each rewrite. The applied diff MUST touch ONLY the matched span — all surrounding
     text and its tashkeel stay BYTE-IDENTICAL. Any rewrite bleeding outside the span ->
     reject, log issue, keep original.
  4. CONSERVATISM: only clear first-person/"our-site" self-references are rewritten.
     Ambiguous cases (author already citing st-takla in 3rd person, or unclear voice) are
     LEFT AS-IS and appended to pending_review[] for a human. NEVER guess.
NOTE (complement): the renderer already strips image-caption boilerplate
  ("St-Takla.org Image:" / "صورة في موقع الأنبا تكلا:"); THIS phase handles BODY PROSE only.
EXAMPLE:
  before: وقد تكلمنا عن هذا الموضوع في موقع الأنبا تكلاهيمانوت
  after:  وقد ورد هذا الموضوع في موقع الأنبا تكلاهيمانوت (st-takla.org)
SELF-CHECK: re-scan finds no first-person st-takla marker that is neither rewritten+logged
  nor in pending_review; every diff is span-bounded; re-run is a no-op.
STOP CONDITIONS: a rewrite's diff escapes the matched span; LLM alters tashkeel/text outside
  the span -> discard edit, log issue, STOP. (All rewrites are human-approved at phase 99.)
OUTPUT: rewritten chapters/*/content.xhtml; state.source_reattribution; state.issues/review.
