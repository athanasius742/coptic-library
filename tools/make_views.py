#!/usr/bin/env python3
"""
make_views.py — Regenerate the by-author/ and by-topic/ views and all browsable,
SEO-friendly README indexes from the canonical books/ tree. Idempotent.

Canonical layout (single source of truth):
    books/<source>/<author-slug>/<book-slug>/        + meta.json  [+ manifest.json]

Generated (never edit by hand — edit meta.json and re-run):
    by-author/<author-slug>/<book-slug>  -> symlink into books/
    by-topic/<topic>/<book-slug>         -> symlink into books/
    README.md, by-author/README.md, by-topic/README.md   (clickable indexes)
    books/.../<book>/README.md                             (per-book page)

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
        m["_rel"] = os.path.relpath(m["_dir"], REPO)
        man_path = os.path.join(m["_dir"], "manifest.json")
        chapters = []
        if os.path.exists(man_path):
            chapters = [c for c in json.load(open(man_path, encoding="utf-8"))
                        if c.get("slug") != "index"]
        m["_chapters"] = chapters
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


def badge(label, msg, color="blue"):
    enc = lambda s: str(s).replace("-", "--").replace(" ", "_")
    return f"https://img.shields.io/badge/{enc(label)}-{enc(msg)}-{color}"


def title_both(b):
    t = b["title"]
    return t + (f" — *{b['title_en']}*" if b.get("title_en") else "")


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text if text.endswith("\n") else text + "\n")


# ------------------------------- per-book ------------------------------
def per_book_readme(b):
    L = [f"# {b['title']}"]
    if b.get("title_en"):
        L.append(f"### {b['title_en']}")
    L.append("")
    L.append(f"**المؤلف / Author:** {b['author']}"
             + (f" · {b['author_en']}" if b.get("author_en") else ""))
    if b.get("series"):
        L.append(f"**السلسلة / Series:** {b['series']}"
                 + (f" · {b.get('series_en','')}" if b.get("series_en") else ""))
    L.append(f"**المصدر / Source:** [{b.get('source','')}]({b.get('source_url','')})")
    L.append(f"**الموضوعات / Topics:** {', '.join(b.get('topics', [])) or '—'}")
    L.append("")
    if b.get("epub"):
        L.append(f"📘 **[Download EPUB / تحميل الكتاب]({b['epub']})**")
        L.append("")
    if b.get("cover") and os.path.exists(os.path.join(b["_dir"], b["cover"])):
        L.append(f'<img src="{b["cover"]}" alt="{b["title"]} — {b.get("title_en","")}" width="320"/>')
        L.append("")
    if b.get("description"):
        L += ["## نبذة", "", b["description"], ""]
    if b.get("description_en"):
        L += ["## Synopsis", "", b["description_en"], ""]
    if b["_chapters"]:
        L += [f"## الفصول / Chapters ({len(b['_chapters'])})", ""]
        for c in b["_chapters"]:
            cdir = f"chapters/{c['order']:02d}-{c['slug']}"
            target = cdir if os.path.isdir(os.path.join(b["_dir"], cdir)) else None
            line = f"{c['order']}. " + (f"[{c['title']}]({target}/)" if target else c["title"])
            L.append(line)
        L.append("")
    L += ["---",
          "*هذا الكتاب مجاني للنشر والتوزيع لخلاص كل نفس. "
          "This book is free to share and distribute for the salvation of every soul.*"]
    write(os.path.join(b["_dir"], "README.md"), "\n".join(L))


# ------------------------------- main ----------------------------------
def main():
    books = load_books()
    if not books:
        sys.exit("No books found (need books/<source>/<author>/<book>/meta.json).")

    reset_dir(BY_AUTHOR)
    reset_dir(BY_TOPIC)
    authors, topics = {}, {}
    for b in books:
        link(b["_dir"], os.path.join(BY_AUTHOR, b["author_slug"], b["slug"]))
        authors.setdefault(b["author_slug"],
                           {"name": b.get("author_en") or b["author"],
                            "name_ar": b["author"], "books": []})["books"].append(b)
        for t in b.get("topics", []):
            link(b["_dir"], os.path.join(BY_TOPIC, t, b["slug"]))
            topics.setdefault(t, []).append(b)
        per_book_readme(b)

    n_b, n_a, n_t = len(books), len(authors), len(topics)

    # ---------------------------- root README --------------------------
    R = [
        "# 📚 Coptic Library · المكتبة القبطية الأرثوذكسية",
        "",
        "> **Free Coptic Orthodox Christian books** — Arabic theology, dogma and "
        "spirituality, preserved as **EPUB** and **HTML**.  ",
        "> **مكتبة مجانية للكتب القبطية الأرثوذكسية** — لاهوت وعقيدة وروحانيات، "
        "بصيغة EPUB و HTML، للنشر والتوزيع لخلاص أكبر عدد من النفوس.",
        "",
        f"![Books]({badge('books', n_b, 'brightgreen')}) "
        f"![Authors]({badge('authors', n_a)}) "
        f"![Topics]({badge('topics', n_t)}) "
        f"![EPUB]({badge('format', 'EPUB + HTML', 'orange')}) "
        f"![License]({badge('content', 'free to share', 'blue')})",
        "",
        "## About / عن المكتبة",
        "",
        "An open, growing archive of Coptic Orthodox books gathered from "
        "[St-Takla.org](https://st-takla.org) and other free sources, re-published as "
        "clean, self-contained **EPUB** files (with the original page-by-page HTML kept "
        "alongside). Every book here is **free to read, copy and share** — distributed "
        "freely for the spiritual benefit and salvation of all.",
        "",
        "أرشيف مفتوح ومتنامٍ للكتب القبطية الأرثوذكسية، مُجمَّع من موقع الأنبا تكلاهيمانوت "
        "ومصادر مجانية أخرى، ومُعاد نشره ككتب EPUB نظيفة ومستقلة، مع الاحتفاظ بصفحات "
        "HTML الأصلية. كل الكتب هنا مجانية للقراءة والنسخ والتوزيع.",
        "",
        "## 📖 Browse / تصفّح",
        "",
        "- **[By author / حسب المؤلف](by-author/README.md)** — "
        + ", ".join(f"[{authors[a]['name']}](by-author/{a}/)" for a in sorted(authors)),
        "- **[By topic / حسب الموضوع](by-topic/README.md)** — "
        + ", ".join(f"[{t}](by-topic/{t}/)" for t in sorted(topics)),
        "",
        "## Books / الكتب",
        "",
        "| الكتاب · Book | المؤلف · Author | الموضوع · Topics | الفصول · Ch. | EPUB |",
        "|---|---|---|:--:|:--:|",
    ]
    for b in books:
        topic_links = ", ".join(f"[{t}](by-topic/{t}/)" for t in b.get("topics", [])) or "—"
        epub = f"[⬇]({b['_rel']}/{b['epub']})" if b.get("epub") else "—"
        R.append(f"| [{title_both(b)}]({b['_rel']}/) | "
                 f"{b['author']}<br/>{b.get('author_en','')} | {topic_links} | "
                 f"{len(b['_chapters']) or '—'} | {epub} |")
    R += [
        "",
        "## Reading the books / كيفية القراءة",
        "",
        "Open any `.epub` in a reader such as Calibre, Apple Books, Google Play Books, "
        "KOReader, Thorium, or any e-reader. The original HTML pages live under each "
        "book's `pages/` and `chapters/` folders.",
        "",
        "## Sources & attribution / المصادر والإسناد",
        "",
        "Texts were digitized and published as HTML by **[St-Takla.org](https://st-takla.org)** "
        "(موقع الأنبا تكلاهيمانوت), the Coptic Orthodox Church reference site. Original "
        "authorship belongs to the respective authors and the Coptic Orthodox Church. "
        "The works are distributed free of charge; this repository preserves and "
        "re-formats them with attribution. See [`NOTICE.md`](NOTICE.md).",
        "",
        "## Tools / الأدوات",
        "",
        "See [`tools/`](tools/): **`sttakla_extract.py`** walks a St-Takla.org book "
        "(following its *next-page* links), saves every page, downloads the cover and "
        "illustrations, and builds a right-to-left EPUB; **`make_views.py`** regenerates "
        "these views and indexes. Code is MIT-licensed — see [`LICENSE`](LICENSE).",
        "",
        "## Keywords",
        "",
        "<sub>Coptic Orthodox books · Coptic Christianity · Arabic Christian theology · "
        "Coptic Orthodox Church · patrology · dogma · original/ancestral sin · free "
        "Christian ebooks · EPUB · كتب قبطية أرثوذكسية · لاهوت · عقيدة · الكتاب المقدس · "
        "آباء الكنيسة · المكتبة القبطية · موقع الأنبا تكلا · "
        + " · ".join(sorted({k for b in books for k in b.get("keywords", [])}))
        + "</sub>",
    ]
    write(os.path.join(REPO, "README.md"), "\n".join(R))

    # ------------------------- by-author/README ------------------------
    A = ["# By Author · حسب المؤلف", "",
         "Authors in this library. Folders here are symlinks into "
         "[`books/`](../books/); each book also has its own page.", ""]
    for a in sorted(authors):
        info = authors[a]
        A.append(f"## {info['name_ar']}")
        A.append(f"*{info['name']}* · `{a}`\n")
        for b in sorted(info["books"], key=lambda x: x["slug"]):
            ep = f' · [EPUB](../{b["_rel"]}/{b["epub"]})' if b.get("epub") else ""
            A.append(f"- [{title_both(b)}](../{b['_rel']}/){ep}")
        A.append("")
    write(os.path.join(BY_AUTHOR, "README.md"), "\n".join(A))

    # ------------------------- by-topic/README -------------------------
    T = ["# By Topic · حسب الموضوع", "",
         "Browse books by subject. Folders here are symlinks into "
         "[`books/`](../books/).", ""]
    for t in sorted(topics):
        T.append(f"## {t}\n")
        for b in sorted(topics[t], key=lambda x: x["slug"]):
            ep = f' · [EPUB](../{b["_rel"]}/{b["epub"]})' if b.get("epub") else ""
            T.append(f"- [{title_both(b)}](../{b['_rel']}/) — "
                     f"{b.get('author_en') or b['author']}{ep}")
        T.append("")
    write(os.path.join(BY_TOPIC, "README.md"), "\n".join(T))

    print(f"Indexed {n_b} book(s): {n_a} author(s), {n_t} topic(s).")
    print("Regenerated: per-book READMEs, by-author/, by-topic/, root README.")


if __name__ == "__main__":
    main()
