#!/usr/bin/env python3
"""
catalog_upsert.py — PLAN §4.8 / phase 90.

Idempotently upsert this book's entry in tools/catalog.json (keyed by book_id),
keeping the existing flat-list shape the web app reads. Crucially it sets
`chapter_links_guess` to the number of CONTENT chapters — the UI's chapterCount
comes from this field, NOT manifest length (PLAN §0.2 gotcha) — and sets
`status` to "draft" by default so the book stays invisible until the human gate
flips it to "verified" (the web filters status === "verified").

Merge-not-clobber: an existing entry keeps its human/crawler-provided fields
(index_url, family, cover_url, title_guess, author_guess) unless re-derivable;
only the pipeline-owned fields are refreshed.

Usage:
  python3 tools/catalog_upsert.py <book-dir> [--status draft|verified]
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state as st
from extract_book import CATALOG


def upsert(book_dir, status):
    meta = st.load_json(st.meta_path(book_dir))
    if not meta:
        raise SystemExit("catalog_upsert: meta.json missing")
    book_id = st.book_id_from_dir(book_dir)
    n_content = st.content_chapter_count(book_dir)
    section = "english" if meta.get("language") == "en" else "arabic"
    derived = {
        "book_id": book_id,
        "index_url": meta.get("source_url", ""),
        "family": "clean",
        "author_slug": st.author_slug(book_dir),
        "book_slug": st.book_slug(book_dir),
        "title_guess": meta.get("title"),
        "author_guess": meta.get("author"),
        "cover_url": None,
        "dest": st.dest_relpath(book_dir),
        "section": section,
        "chapter_links_guess": n_content,
        "status": status,
    }

    recs = st.load_json(CATALOG, [])
    found = None
    for r in recs:
        if r.get("book_id") == book_id:
            found = r
            break
    if found is None:
        recs.append(derived)
        action = "created"
    else:
        # merge-not-clobber: keep existing crawler/human fields; refresh the
        # pipeline-owned ones (dest, slugs, section, count, status).
        for k in ("dest", "author_slug", "book_slug", "section",
                  "chapter_links_guess", "status"):
            found[k] = derived[k]
        for k in ("index_url", "family", "title_guess", "author_guess", "cover_url"):
            if not found.get(k) and derived.get(k):
                found[k] = derived[k]
        action = "updated"

    st.atomic_write_json(CATALOG, recs)
    return action, n_content, status


def main():
    ap = argparse.ArgumentParser(description="Upsert this book's tools/catalog.json entry.")
    ap.add_argument("book_dir")
    ap.add_argument("--status", choices=["draft", "verified"], default="draft")
    args = ap.parse_args()
    book_dir = os.path.abspath(args.book_dir)

    action, n, status = upsert(book_dir, args.status)
    print(f"catalog_upsert: {action} entry (status={status}, chapter_links_guess={n})")

    state = st.load_state(book_dir)
    if state is not None:
        st.set_phase(state, "catalog", "done", st.compute_source_hash(book_dir))
        st.save_state(book_dir, state)


if __name__ == "__main__":
    main()
