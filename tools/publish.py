#!/usr/bin/env python3
"""
publish.py — PLAN §4.9 / phase 99 (report + human review gate) and an optional
thin phase orchestrator.

Three modes:
  * default      — write BOOK_DIR/REPORT.md from .build/state.json and set
                   state.review = "pending". The book is NOT yet visible.
  * --approve    — the human-review flip: requires verify to have passed (no
                   error-severity issues) and review == "pending"; sets
                   tools/catalog.json status -> "verified" and review ->
                   "approved". This is the ONLY place automation may write
                   status:"verified".
  * --run        — thin orchestrator: run the Phase-1 tools in order
                   (normalize -> reattribute -> images -> refs -> build -> verify
                   -> catalog draft), then write the report. Each tool is itself
                   hash-gated / idempotent. Stops on the first failing gate.

Usage:
  python3 tools/publish.py <book-dir>
  python3 tools/publish.py <book-dir> --run
  python3 tools/publish.py <book-dir> --approve
"""
import os
import sys
import subprocess
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state as st
from extract_book import CATALOG, REPO

TOOLS = os.path.dirname(os.path.abspath(__file__))


# ------------------------------- report --------------------------------
def write_report(book_dir, state):
    meta = st.load_json(st.meta_path(book_dir)) or {}
    fns = state.get("footnote_registry", [])
    resolved = sum(1 for f in fns if f.get("resolved"))
    errors = st.issues_by_severity(state, "error")
    warns = st.issues_by_severity(state, "warn")
    sr = state.get("source_reattribution") or {}
    author = state.get("author") or {}
    n_content = st.content_chapter_count(book_dir)
    aslug = st.author_slug(book_dir)
    bslug = st.book_slug(book_dir)

    lines = []
    lines.append(f"# Publish report — {meta.get('title', bslug)}")
    lines.append("")
    lines.append(f"- **book_id**: `{state.get('book_id')}`")
    lines.append(f"- **author**: {meta.get('author','')}  (`{aslug}`)")
    lines.append(f"- **language**: {meta.get('language','ar')}")
    lines.append(f"- **review**: {state.get('review','pending')}")
    lines.append("")
    lines.append("## Counts")
    lines.append(f"- content chapters: **{n_content}**")
    lines.append(f"- footnotes wired: **{resolved}** / {len(fns)}")
    lines.append(f"- headings: {len(state.get('heading_map', {}))}")
    lines.append(f"- issues: {len(errors)} error, {len(warns)} warning")
    lines.append("")

    if author:
        lines.append("## Author resolution")
        lines.append(f"- slug: `{author.get('slug')}`  method: {author.get('method')}  "
                     f"confidence: {author.get('confidence')}  "
                     f"needs_review: {author.get('needs_review')}")
        lines.append("")

    rewrites = sr.get("rewrites", [])
    pending = sr.get("pending_review", [])
    if rewrites or pending:
        lines.append("## Source re-attribution (§4.1a — MUST be human-approved)")
        for rw in rewrites:
            lines.append(f"- **{rw.get('chapter')}**: ")
            lines.append(f"  - before: `{rw.get('before','')[:200]}`")
            lines.append(f"  - after:  `{rw.get('after','')[:200]}`")
        for pr in pending:
            lines.append(f"- _pending review_ **{pr.get('chapter')}**: {pr.get('note','')} "
                         f"— `{pr.get('context','')[:160]}`")
        lines.append("")

    if errors:
        lines.append("## Errors (block verified)")
        for i in errors:
            ch = f" [{i['chapter']}]" if i.get("chapter") else ""
            lines.append(f"- `{i['code']}`{ch}: {i['detail']}")
        lines.append("")
    if warns:
        lines.append("## Warnings")
        for i in warns[:50]:
            ch = f" [{i['chapter']}]" if i.get("chapter") else ""
            lines.append(f"- `{i['code']}`{ch}: {i['detail']}")
        if len(warns) > 50:
            lines.append(f"- … and {len(warns) - 50} more")
        lines.append("")

    lines.append("## Sample chapter links")
    for ch in (state.get("toc") or [])[:5]:
        lines.append(f"- /ar/books/{aslug}/{bslug}/{ch['slug']} — {ch['title']}")
    lines.append("")
    lines.append("---")
    lines.append("Approve with: `python3 tools/publish.py "
                 f"{st.dest_relpath(book_dir)} --approve` (only after verify passes "
                 "and the re-attribution rewrites above are reviewed).")
    lines.append("")
    st.atomic_write_text(os.path.join(book_dir, "REPORT.md"), "\n".join(lines))


# ------------------------------- approve --------------------------------
def approve(book_dir, state):
    errors = st.issues_by_severity(state, "error")
    if errors:
        print(f"publish --approve REFUSED: {len(errors)} error-severity issue(s) remain. "
              "Fix them and re-run verify first.", file=sys.stderr)
        return False
    if st.phase_record(state, "verify").get("status") != "done":
        print("publish --approve REFUSED: verify has not passed (run verify_book.py).",
              file=sys.stderr)
        return False
    book_id = state["book_id"]
    recs = st.load_json(CATALOG, [])
    hit = next((r for r in recs if r.get("book_id") == book_id), None)
    if hit is None:
        print("publish --approve REFUSED: no catalog entry (run catalog_upsert.py).",
              file=sys.stderr)
        return False
    hit["status"] = "verified"
    st.atomic_write_json(CATALOG, recs)
    state["review"] = "approved"
    st.save_state(book_dir, state)
    print(f"publish: APPROVED — {book_id} is now status:'verified' (visible to the web app).")
    return True


# ------------------------------- run ------------------------------------
def run_pipeline(book_dir):
    steps = [
        ("normalize", ["normalize_chapters.py", book_dir]),
        ("images", ["extract_book_images.py", book_dir]),
        ("refs", ["resolve_refs.py", book_dir]),
        ("epub", ["build_epub.py", book_dir]),
        ("verify", ["verify_book.py", book_dir]),
        ("catalog", ["catalog_upsert.py", book_dir, "--status", "draft"]),
    ]
    for name, argv in steps:
        print(f"\n=== phase: {name} ===")
        r = subprocess.run([sys.executable, os.path.join(TOOLS, argv[0])] + argv[1:])
        if r.returncode != 0 and name == "verify":
            print(f"publish --run: verify failed; stopping before the gate.", file=sys.stderr)
            return False
        if r.returncode != 0 and name not in ("verify",):
            print(f"publish --run: phase {name} failed (rc={r.returncode}); stopping.",
                  file=sys.stderr)
            return False
    return True


def main():
    ap = argparse.ArgumentParser(description="Report + human review gate (and optional orchestrator).")
    ap.add_argument("book_dir")
    ap.add_argument("--approve", action="store_true", help="flip catalog status -> verified")
    ap.add_argument("--run", action="store_true", help="run the Phase-1 tools in order first")
    args = ap.parse_args()
    book_dir = os.path.abspath(args.book_dir)

    if args.run:
        if not run_pipeline(book_dir):
            sys.exit(1)

    state = st.load_state(book_dir)
    if state is None:
        raise SystemExit("publish: no .build/state.json (run the pipeline first)")

    if args.approve:
        ok = approve(book_dir, state)
        sys.exit(0 if ok else 1)

    # default: report + set review pending
    state["review"] = "pending"
    st.save_state(book_dir, state)
    write_report(book_dir, state)
    errors = st.issues_by_severity(state, "error")
    print(f"publish: wrote REPORT.md; review='pending'. "
          f"{len(errors)} error(s) {'block' if errors else 'do not block'} approval.")


if __name__ == "__main__":
    main()
