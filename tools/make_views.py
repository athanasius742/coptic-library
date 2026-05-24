#!/usr/bin/env python3
"""
make_views.py — Regenerate the catalog/index markdown from the canonical books/
tree. Books are stored in exactly ONE place; the catalog files are just tables of
links into books/. Idempotent — run whenever you add a book or change metadata.

Canonical layout (single source of truth):
    books/<source>/<author-slug>/<book-slug>/        + meta.json  [+ manifest.json]

Generated (never edit by hand — edit meta.json and re-run):
    README.md         root index (catalog table + intro)
    by-author.md      books grouped by author (tables of links into books/)
    by-topic.md       books grouped by topic  (tables of links into books/)
    books/.../<book>/README.md   per-book page (synopsis + chapter list)

Run from anywhere:   python3 tools/make_views.py
"""
import os, sys, json, glob

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOKS = os.path.join(REPO, "books")


def load_books():
    books = []
    for meta_path in glob.glob(os.path.join(BOOKS, "*", "*", "*", "meta.json")):
        m = json.load(open(meta_path, encoding="utf-8"))
        m["_dir"] = os.path.dirname(meta_path)
        m["_rel"] = os.path.relpath(m["_dir"], REPO)      # repo-root-relative path
        man_path = os.path.join(m["_dir"], "manifest.json")
        m["_chapters"] = ([c for c in json.load(open(man_path, encoding="utf-8"))
                           if c.get("slug") != "index"]
                          if os.path.exists(man_path) else [])
        books.append(m)
    return sorted(books, key=lambda b: (b.get("author_slug", ""), b.get("slug", "")))


def badge(label, msg, color="blue"):
    enc = lambda s: str(s).replace("-", "--").replace(" ", "_")
    return f"https://img.shields.io/badge/{enc(label)}-{enc(msg)}-{color}"


def title_both(b):
    return b["title"] + (f" — *{b['title_en']}*" if b.get("title_en") else "")


def epub_cell(b):
    return f"[⬇ EPUB]({b['_rel']}/{b['epub']})" if b.get("epub") else "—"


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text if text.endswith("\n") else text + "\n")


# ------------------------------- per-book ------------------------------
def per_book_readme(b):
    L = [f"# {b['title']}"]
    if b.get("title_en"):
        L.append(f"### {b['title_en']}")
    L += ["",
          f"**المؤلف / Author:** {b['author']}"
          + (f" · {b['author_en']}" if b.get("author_en") else "")]
    if b.get("series"):
        L.append(f"**السلسلة / Series:** {b['series']}"
                 + (f" · {b.get('series_en','')}" if b.get("series_en") else ""))
    L.append(f"**المصدر / Source:** [{b.get('source','')}]({b.get('source_url','')})")
    L.append(f"**الموضوعات / Topics:** {', '.join(b.get('topics', [])) or '—'}")
    L.append("")
    if b.get("epub"):
        L += [f"📘 **[Download EPUB / تحميل الكتاب]({b['epub']})**", ""]
    if b.get("cover") and os.path.exists(os.path.join(b["_dir"], b["cover"])):
        L += [f'<img src="{b["cover"]}" alt="{b["title"]} — {b.get("title_en","")}" width="320"/>', ""]
    if b.get("description"):
        L += ["## نبذة", "", b["description"], ""]
    if b.get("description_en"):
        L += ["## Synopsis", "", b["description_en"], ""]
    if b["_chapters"]:
        L += [f"## الفصول / Chapters ({len(b['_chapters'])})", ""]
        for c in b["_chapters"]:
            cdir = f"chapters/{c['order']:02d}-{c['slug']}"
            target = cdir if os.path.isdir(os.path.join(b["_dir"], cdir)) else None
            L.append(f"{c['order']}. " + (f"[{c['title']}]({target}/)" if target else c["title"]))
        L.append("")
    L += ["---",
          "*هذا الكتاب مجاني للنشر والتوزيع لخلاص كل نفس. "
          "This book is free to share and distribute for the salvation of every soul.*"]
    write(os.path.join(b["_dir"], "README.md"), "\n".join(L))


# -------------------------------- main ---------------------------------
def main():
    books = load_books()
    if not books:
        sys.exit("No books found (need books/<source>/<author>/<book>/meta.json).")

    authors, topics = {}, {}
    for b in books:
        authors.setdefault(b["author_slug"],
                           {"name": b.get("author_en") or b["author"],
                            "name_ar": b["author"], "books": []})["books"].append(b)
        for t in b.get("topics", []):
            topics.setdefault(t, []).append(b)
        per_book_readme(b)

    n_b, n_a, n_t = len(books), len(authors), len(topics)

    # ---------------------------- by-author.md -------------------------
    A = ["# By Author · حسب المؤلف", "",
         "Every book is stored once under [`books/`](books/). This page groups them "
         "by author — click any title to open the book.", ""]
    for a in sorted(authors):
        info = authors[a]
        A += [f"## {info['name_ar']}",
              f"*{info['name']}* · `{a}`", "",
              "| الكتاب · Book | الموضوعات · Topics | الفصول · Ch. | تحميل · Download |",
              "|---|---|:--:|:--:|"]
        for b in sorted(info["books"], key=lambda x: x["slug"]):
            A.append(f"| [{title_both(b)}]({b['_rel']}/) "
                     f"| {', '.join(b.get('topics', [])) or '—'} "
                     f"| {len(b['_chapters']) or '—'} | {epub_cell(b)} |")
        A.append("")
    write(os.path.join(REPO, "by-author.md"), "\n".join(A))

    # ---------------------------- by-topic.md --------------------------
    T = ["# By Topic · حسب الموضوع", "",
         "Every book is stored once under [`books/`](books/). This page groups them "
         "by subject — click any title to open the book.", ""]
    for t in sorted(topics):
        T += [f"## {t}", "",
              "| الكتاب · Book | المؤلف · Author | الفصول · Ch. | تحميل · Download |",
              "|---|---|:--:|:--:|"]
        for b in sorted(topics[t], key=lambda x: x["slug"]):
            T.append(f"| [{title_both(b)}]({b['_rel']}/) "
                     f"| {b.get('author_en') or b['author']} "
                     f"| {len(b['_chapters']) or '—'} | {epub_cell(b)} |")
        T.append("")
    write(os.path.join(REPO, "by-topic.md"), "\n".join(T))

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
        "alongside). Every book is stored in **one** place under [`books/`](books/) and "
        "is **free to read, copy and share** — distributed freely for the spiritual "
        "benefit and salvation of all.",
        "",
        "أرشيف مفتوح ومتنامٍ للكتب القبطية الأرثوذكسية، مُجمَّع من موقع الأنبا تكلاهيمانوت "
        "ومصادر مجانية أخرى، ومُعاد نشره ككتب EPUB نظيفة ومستقلة، مع الاحتفاظ بصفحات "
        "HTML الأصلية. كل كتاب محفوظ في مكان واحد، وكلها مجانية للقراءة والنسخ والتوزيع.",
        "",
        "## 📖 Browse / تصفّح",
        "",
        "- **[By author / حسب المؤلف](by-author.md)**",
        "- **[By topic / حسب الموضوع](by-topic.md)**",
        "",
        "## Books / الكتب",
        "",
        "| الكتاب · Book | المؤلف · Author | الموضوع · Topics | الفصول · Ch. | EPUB |",
        "|---|---|---|:--:|:--:|",
    ]
    for b in books:
        R.append(f"| [{title_both(b)}]({b['_rel']}/) "
                 f"| {b['author']}<br/>{b.get('author_en','')} "
                 f"| {', '.join(b.get('topics', [])) or '—'} "
                 f"| {len(b['_chapters']) or '—'} | {epub_cell(b)} |")
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
        "this README and the `by-author.md` / `by-topic.md` catalogs. Code is "
        "MIT-licensed — see [`LICENSE`](LICENSE).",
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

    print(f"Indexed {n_b} book(s): {n_a} author(s), {n_t} topic(s).")
    print("Regenerated: README.md, by-author.md, by-topic.md, per-book READMEs.")


if __name__ == "__main__":
    main()
