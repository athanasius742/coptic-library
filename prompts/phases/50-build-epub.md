# PHASE 50 — Build the EPUB from canonical sources (no drift)
PRECONDITIONS: normalized + ref-resolved content.xhtml; images/ present; meta+manifest valid.
RUN (deterministic, no network, atomic): python3 tools/build_epub.py <BOOK_DIR>
  - read EXISTING chapters/<NN-slug>/content.xhtml (inner <body> + <h1> title);
  - wrap via page_xhtml + style.css (RTL CSS for ar, LTR for en);
  - copy referenced images/* into OEBPS/images/; embed cover.jpg;
  - assemble content.opf (page-progression-direction from language), nav.xhtml, toc.ncx
    from manifest.order + meta; mimetype stored-first; zip atomically to <book-slug>.epub.
VALIDATE: always run the in-repo validate_epub (zip/mimetype/well-formed/refs/>=1 chapter/
  no nav chrome). If epubcheck.jar present: java -jar epubcheck.jar <epub> ; FATAL/ERROR=STOP,
  WARN -> REPORT.md. If absent: log "epubcheck skipped". Fallback: ebook-convert (Calibre),
  flagged as fallback-built.
SELF-CHECK: validate_epub passes; round-trip text diff (with tashkeel) ≈ 0 per chapter.
OUTPUT: <BOOK_DIR>/<book-slug>.epub; state.phases.epub=done.
