# PHASE 30 — Resolve images (extract, manifest, alt-text, integrity)
ROLE: pull/resize the book's images into images/, build the image_manifest, and verify every
  <img> reference resolves to a present file with non-empty alt. Owner: CODE; LLM only to
  author missing alt text. RUN ORDER: BEFORE phase 20 (images and refs both rewrite
  content.xhtml; do images first, then refs, then recompute source_hash).
PRECONDITIONS: normalized content.xhtml (phase 10 done); the book <slug>.epub present
  (Phase 1 source of raster images). Phase 2 images come from tools/pdf_intake.py (§5.5).
RUN (deterministic, NO network): python3 tools/extract_book_images.py <BOOK_DIR>
  - greps src="images/<name>" from chapters/*/content.xhtml; pulls matching OEBPS/images/<name>
    from the book .epub; resizes shrink-only via ImageMagick (magick -resize '720x720>'
    -strip -quality 82) into images/ (content-addressed img_<md5(...)[:12]>.<ext>, §7);
  - writes images/_missing.json for any referenced image absent from the epub.
  - BUILD the image_manifest in .build/state.json (Appendix C / image-manifest.schema.json):
    [{name, referenced_in[], present, bytes, alt_present}].
INTEGRITY (code): every src="images/X" in content.xhtml resolves to a PRESENT file; every
  <img> has non-empty alt (preserve scraped bilingual alt). 
LLM (judgment, rare): author alt text ONLY where it is genuinely missing; log each one.
MISSING IMAGES: record in image_manifest + images/_missing.json + state.issues. NEVER silently
  drop the <img> — a missing image is an issue for the human gate, not a deletion.
SELF-CHECK: referenced == present (or logged missing); every <img> has alt; re-run is a no-op
  (content-addressed names, hash-gated).
ON FAILURE: log to state.issues and STOP if references cannot be satisfied and no fallback.
OUTPUT: images/*, images/_missing.json (if any), state.image_manifest, state.issues;
  state.phases.images=done (+input_hash). NEXT: phase 20 (resolve-references).
