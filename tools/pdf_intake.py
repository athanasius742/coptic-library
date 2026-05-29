#!/usr/bin/env python3
"""
pdf_intake.py — PLAN §5 / phase 05 (PHASE 2, FUTURE — deferred behind §13).

Goal: turn a physical-book PDF into the SAME canonical shape as Phase 1
(chapters/<NN-slug>/content.xhtml + images/img_<hash>.<ext> + manifest.json +
meta.json + cover.jpg), then rejoin Phase 1 at phase 20 (resolve-references).

ENGINE RULE (non-negotiable, §5.3): a CLOUD VISION-LLM does ALL OCR AND ALL
STRUCTURE for scans. PyMuPDF (fitz) does DETERMINISTIC MECHANICS ONLY — triage,
born-digital text-layer extraction, 300-DPI rasterization, embedded-image
extraction, and figure-bbox cropping. There is NO Tesseract / OCRmyPDF / Surya /
QARI / Docling anywhere in this phase.

This module is intentionally a STUB. Phase 2 is deferred pending human decisions
(PLAN §13.4/§13.5): the OCR model (Claude vs Gemini) and budget/spend cap, and
approval to add `pymupdf` + `pyarabic`. Implementing it before those are settled
would hard-wire choices the plan explicitly parks for a human.

When unblocked, implement (deterministic PyMuPDF mechanics + vision-LLM judgment):
  §5.1 triage per page (chars/image-area/Arabic sanity) -> digital|scanned|fake;
  §5.2 born-digital get_text("dict") OR §5.3 rasterize -> vision-LLM OCR;
  §5.4 vision-LLM reading order/region labels/chapter boundaries (+ dedup
       repeated headers/footers); cross-check doc.get_toc();
  §5.5 extract/crop figures at LLM bboxes -> images/img_<md5>.<ext> (magick 720 q82);
  §5.6 structure into the Appendix-D content.xhtml subset (diff-gated);
  §5.7 title-page metadata -> meta.json (honorifics/dual-dating/numerals);
  §5.8 rejoin Phase 1 at phase 20.

Usage (once implemented):
  python3 tools/pdf_intake.py <book.pdf> --out <book-dir>
"""
import sys
import argparse


def main():
    ap = argparse.ArgumentParser(description="PDF intake -> canonical shape (Phase 2, deferred).")
    ap.add_argument("pdf")
    ap.add_argument("--out", required=True)
    ap.parse_args()
    sys.exit(
        "pdf_intake.py is a deferred Phase-2 stub (PLAN §5, §13). It needs human\n"
        "decisions first: the vision-LLM OCR model (Claude vs Gemini) + budget cap,\n"
        "and approval to add the `pymupdf` + `pyarabic` dependencies. See\n"
        "prompts/phases/05-pdf-intake.md for the engine contract."
    )


if __name__ == "__main__":
    main()
