#!/usr/bin/env python3
"""
make_views.py — Regenerate the by-author/ and by-topic/ views and the browsable
README indexes from the canonical books/ tree. Idempotent: safe to re-run anytime.

Canonical layout (single source of truth):
    books/<source>/<author-slug>/<book-slug>/        + meta.json

Generated (never edit by hand):
    by-author/<author-slug>/<book-slug>  -> symlink into books/
    by-topic/<topic>/<book-slug>         -> symlink into books/
    README.md, by-author/README.md, by-topic/README.md   (clickable indexes)

A book is included once it has a meta.json. Topics come from meta.json "topics".
Run from anywhere:   python3 tools/make_views.py
"""
import os, sys, json, shutil, glob

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOKS = os.path.join(REPO, "books")
BY_AUTHOR = os.path.join(REPO, "by-author")
BY_TOPIC = os.path.join(REPO, "by-topic")


def load_books():
    books = []
    for meta_path in glob.glob(os.path.join(BOOKS, "*", "*", "*", "meta.json")):
        m = json.load(open(meta_path, encoding="utf-8"))
        m["_dir"] = os.path.dirname(meta_path)
        books.append(m)
    return sorted(books, key=lambda b: (b.get("author_slug", ""), b.get("slug", "")))


def reset_dir(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)


def link(target_dir, link_path):
    os.makedirs(os.path.dirname(link_path), exist_ok=True)
    rel = os.path.relpath(target_dir, os.path.dirname(link_path))
    if os.path.islink(link_path) or os.path.exists(link_path):
        os.remove(link_path)
    os.symlink(rel, link_path)


def md_link(text, path_from_repo):
    return f"[{text}]({path_from_repo})"


def main():
    books = load_books()
    if not books:
        sys.exit("No books found (need books/<source>/<author>/<book>/meta.json).")

    reset_dir(BY_AUTHOR)
    reset_dir(BY_TOPIC)

    authors, topics = {}, {}
    for b in books:
        a_slug, b_slug = b["author_slug"], b["slug"]
        link(b["_dir"], os.path.join(BY_AUTHOR, a_slug, b_slug))
        authors.setdefault(a_slug, {"name": b.get("author_en") or b["author"], "books": []})
        authors[a_slug]["books"].append(b)
        for t in b.get("topics", []):
            link(b["_dir"], os.path.join(BY_TOPIC, t, b_slug))
            topics.setdefault(t, []).append(b)

    def book_line(b, base):
        rel = os.path.relpath(b["_dir"], os.path.join(REPO, base.split("/")[0])) if base else ""
        # link relative to the README's own directory
        title = f'{b["title"]}' + (f' — *{b["title_en"]}*' if b.get("title_en") else "")
        bookrel = os.path.relpath(b["_dir"], REPO)
        epub = b.get("epub")
        epub_link = f' · [EPUB]({bookrel}/{epub})' if epub else ""
        return title, bookrel, epub_link

    # ---- root README index ----
    lines = ["# Coptic Library", "",
             "A mono-repo archive of books extracted from St-Takla.org and other sources.",
             "Each book is stored **once** under `books/`; `by-author/` and `by-topic/`",
             "are symlink views into it (plus these indexes for web browsing).", "",
             f"**{len(books)} book(s)** · **{len(authors)} author(s)** · **{len(topics)} topic(s)**", "",
             "## Browse", "",
             "- [By author](by-author/README.md)",
             "- [By topic](by-topic/README.md)", "",
             "## All books", ""]
    lines.append("| Title | Author | Topics | Source |")
    lines.append("|---|---|---|---|")
    for b in books:
        bookrel = os.path.relpath(b["_dir"], REPO)
        t = b["title"] + (f" — *{b['title_en']}*" if b.get("title_en") else "")
        topic_links = ", ".join(b.get("topics", [])) or "—"
        src = f'[{b.get("source","")}]({b.get("source_url","")})' if b.get("source_url") else b.get("source", "")
        lines.append(f'| [{t}]({bookrel}/) | {b.get("author_en") or b["author"]} | {topic_links} | {src} |')
    lines += ["", "## Tools", "",
              "See [`tools/`](tools/) — `sttakla_extract.py` (walk + build EPUB) and",
              "`make_views.py` (regenerate these views/indexes). Run `make_views.py` after adding a book.", ""]
    open(os.path.join(REPO, "README.md"), "w", encoding="utf-8").write("\n".join(lines))

    # ---- by-author/README.md ----
    al = ["# By Author", ""]
    for a_slug in sorted(authors):
        info = authors[a_slug]
        al.append(f"## {info['name']}  \n`{a_slug}`\n")
        for b in sorted(info["books"], key=lambda x: x["slug"]):
            bookrel = os.path.relpath(b["_dir"], REPO)
            t = b["title"] + (f" — *{b['title_en']}*" if b.get("title_en") else "")
            al.append(f'- [{t}](../{bookrel}/)' + (f' · [EPUB](../{bookrel}/{b["epub"]})' if b.get("epub") else ""))
        al.append("")
    open(os.path.join(BY_AUTHOR, "README.md"), "w", encoding="utf-8").write("\n".join(al))

    # ---- by-topic/README.md ----
    tl = ["# By Topic", ""]
    for t in sorted(topics):
        tl.append(f"## {t}\n")
        for b in sorted(topics[t], key=lambda x: x["slug"]):
            bookrel = os.path.relpath(b["_dir"], REPO)
            title = b["title"] + (f" — *{b['title_en']}*" if b.get("title_en") else "")
            tl.append(f'- [{title}](../{bookrel}/) — {b.get("author_en") or b["author"]}'
                      + (f' · [EPUB](../{bookrel}/{b["epub"]})' if b.get("epub") else ""))
        tl.append("")
    open(os.path.join(BY_TOPIC, "README.md"), "w", encoding="utf-8").write("\n".join(tl))

    print(f"Indexed {len(books)} book(s): {len(authors)} author(s), {len(topics)} topic(s).")
    print("Regenerated: by-author/, by-topic/, README.md (+ per-view READMEs).")


if __name__ == "__main__":
    main()
