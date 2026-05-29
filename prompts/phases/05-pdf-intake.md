# PHASE 05 — PDF intake (Phase 2 ONLY) -> canonical shape, then rejoin at phase 20
PRECONDITIONS: input is a PDF (routed here by phase 00); --out <BOOK_DIR> chosen.
GOAL: emit Phase-1-shaped chapters/<NN-slug>/content.xhtml + images/img_<hash>.<ext> +
  manifest.json + meta.json + cover.jpg, then CONTINUE at phase 20 (resolve-references).
ENGINE RULE (non-negotiable): a CLOUD VISION-LLM (Claude or Gemini) does ALL OCR AND
  ALL STRUCTURE for scans. PyMuPDF does DETERMINISTIC MECHANICS ONLY. There is NO
  Tesseract / OCRmyPDF / Surya / QARI / Docling anywhere in this phase.
RUN (deterministic plumbing, no network): python3 tools/pdf_intake.py <book.pdf> --out <BOOK_DIR>
  PyMuPDF (fitz) does ONLY:
    (a) TRIAGE per page: char count, image-area coverage, Arabic sanity check ->
        born-digital vs scanned vs fake-text-layer (§5.1);
    (b) BORN-DIGITAL: extract the existing text layer (get_text("dict"), positioned
        blocks/lines/spans+bbox) — verbatim source; no re-OCR;
    (c) SCANNED: rasterize pages to images (get_pixmap(dpi=300)) to feed the vision-LLM;
    (d) extract EMBEDDED raster images (extract_image(xref) / pdfimages -all);
    (e) CROP figure regions at the LLM-provided bounding boxes; ImageMagick resizes
        ('720x720>' -strip -quality 82) to images/img_<md5(...)[:12]>.<ext> (§7).
VISION-LLM (OCR + structure + judgment):
  - SCANNED OCR: send the rasterized page images; instruct: transcribe EXACTLY, preserve
    ALL tashkeel/diacritics, do NOT hallucinate/summarize/translate/reorder, return plain
    text in natural RTL reading order, MARK uncertain/illegible spans.
  - STRUCTURE: return RTL-correct reading order, region labels (heading/body/footnote/
    caption/figure/page-header-footer), chapter boundaries, and figure BOUNDING BOXES +
    captions. Running headers/footers/page numbers: labelled & excluded by the LLM, PLUS a
    deterministic repeated-line dedup strips recurring top/bottom lines.
  - BORN-DIGITAL: infer structure FROM PyMuPDF's positioned text (do NOT re-OCR digital pages).
  - STRUCTURE INTO content.xhtml: per-chapter Appendix D subset (<h1> title + <h2>+ sections,
    <p>, st-takla footnote idiom, image-wrapper/<img images/...>), dir="rtl" + <span dir="ltr">
    for genuine LTR runs; "do not invent text".
GUARD (no blind trust): the vision-LLM OCR text is the "source" for all §10 round-trip checks
  (it plays the role scraped HTML plays in Phase 1); any later LLM edit to it is diff-gated
  (§2). Surface LLM-flagged low-confidence/uncertain spans as state.issues for human review.
METADATA: rasterize first ~3 + last ~2 pages -> vision-LLM -> meta.json (honorifics, dual
  dating, Eastern-Arabic numerals, edition); cross-check catalog.json for duplicates (§5.7).
SELF-CHECK: directory is shape-identical to Phase 1; manifest.order == files on disk;
  every <img> ref is images/<file>; re-run is a no-op (content-addressed images, hash-gated).
ON FAILURE / STOP: illegible scan, no extractable text, or OCR consistency failure ->
  log state.issues and STOP for human review.
OUTPUT: chapters/*/content.xhtml + images/* + manifest.json + meta.json + cover.jpg;
  state.phase="pdf", phases.pdf_intake=done. NEXT: continue at phase 20 (§5.8).
