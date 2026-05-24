# Tools

Scripts for extracting books into this archive and maintaining its structure.

Requires Python 3 with `beautifulsoup4` and `lxml`:

```bash
pip install beautifulsoup4 lxml
```

## `sttakla_extract.py` — extract a St-Takla.org book

Walks a book by following its `<a id="next">` chain, saves every page (decoded
from windows-1256 to UTF-8), organizes per-chapter directories, downloads the
cover (`og:image`) and inline illustrations, and builds a right-to-left EPUB.

```bash
python3 tools/sttakla_extract.py \
    https://st-takla.org/books/anba-raphael/i-willingly-ate/index.html \
    --out books/st-takla.org/anba-raphael/i-willingly-ate
```

Title, author, cover and the first content page are auto-detected from the index
page; override with `--title`, `--author`, `--start`, `--slug`. Use `--no-epub`
to only fetch pages. Be polite: `--delay` defaults to 1s between requests.

After extracting, add a `meta.json` to the book folder (see existing books for
the schema — `slug`, `title`, `author_slug`, `source`, `topics`, `epub`, …) and
run `make_views.py`.

> This extractor targets the St-Takla.org page structure. Other sources need
> their own extractor; the EPUB builder inside is largely source-agnostic.

## `make_views.py` — regenerate views & indexes

Rebuilds `by-author/` and `by-topic/` (symlinks into `books/`) and the browsable
`README.md` indexes from each book's `meta.json`. Idempotent — run it whenever you
add a book or change topics:

```bash
python3 tools/make_views.py
```

`by-author/` and `by-topic/` are **generated** — don't edit them by hand; edit a
book's `meta.json` and re-run.
