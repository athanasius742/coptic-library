#!/usr/bin/env python3
"""
preflight.py — PLAN §4.0 / phase 00.

Deterministic triage: assert a book dir has the Phase-1 preconditions, detect the
available tools (§0.8), determine the phase ("html" — a PDF input routes to
Phase 2 / phases/05-pdf-intake.md), and init/load .build/state.json with a fresh
source_hash. STOPs precisely on a missing precondition; never guesses paths.

Usage:
  python3 tools/preflight.py <book-dir>
"""
import os
import sys
import shutil
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state as st


def detect_tools():
    return {
        "magick": bool(shutil.which("magick")),
        "ebook-convert": bool(shutil.which("ebook-convert")),
        "java": bool(shutil.which("java")),
        "epubcheck": os.path.exists(os.path.join(st.REPO, "tools", "epubcheck.jar")),
    }


def main():
    ap = argparse.ArgumentParser(description="Preflight: assert preconditions + init state.")
    ap.add_argument("book_dir")
    args = ap.parse_args()
    book_dir = os.path.abspath(args.book_dir)

    if not os.path.isdir(book_dir):
        sys.exit(f"preflight STOP: not a directory: {book_dir}")

    # PDF intake (Phase 2) routing
    import glob
    pdfs = glob.glob(os.path.join(book_dir, "*.pdf"))
    has_content = bool(st.content_paths(book_dir))
    has_pages_epub = (os.path.isdir(os.path.join(book_dir, "pages"))
                      and glob.glob(os.path.join(book_dir, "*.epub")))

    if pdfs and not has_content and not has_pages_epub:
        print("preflight: PDF input detected and no extracted chapters -> Phase 2.")
        print("  NEXT: prompts/phases/05-pdf-intake.md (tools/pdf_intake.py)")
        sys.exit(2)

    # Phase 1 preconditions
    problems = []
    if not os.path.exists(st.meta_path(book_dir)):
        problems.append("meta.json missing")
    if not os.path.exists(st.manifest_path(book_dir)):
        problems.append("manifest.json missing")
    if not has_content and not has_pages_epub:
        problems.append("no chapters/*/content.xhtml and no pages/*+*.epub to (re)build them")
    if not os.path.exists(os.path.join(book_dir, "cover.jpg")):
        problems.append("cover.jpg missing (download button + EPUB cover will be absent)")

    tools = detect_tools()
    state = st.init_state(book_dir, phase="html")
    st.set_phase(state, "preflight", "done" if not [p for p in problems if "missing" in p and "cover" not in p] else "failed",
                 st.compute_source_hash(book_dir))
    st.save_state(book_dir, state)

    print(f"preflight: phase=html  book_id={state['book_id']}")
    print(f"  tools: {tools}")
    print(f"  chapters: {st.content_chapter_count(book_dir)}  source_hash={state['source_hash'][:12]}")
    hard = [p for p in problems if "cover.jpg" not in p]
    for p in problems:
        sev = "WARN" if "cover.jpg" in p else "STOP"
        print(f"  {sev}: {p}")
    if hard:
        sys.exit(f"preflight STOP: {len(hard)} hard precondition(s) failed")
    print("preflight: OK -> proceed to phase 10 (normalize)")


if __name__ == "__main__":
    main()
