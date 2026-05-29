#!/usr/bin/env python3
"""
Extract chapter images from the per-book .epub files (where the scraper saved
them) into a web-servable `<book>/images/` directory, resizing each down to a
web-friendly size with ImageMagick.

No network is used: the originals already live inside the local EPUBs as
OEBPS/images/img_<md5(remote_url)[:12]>.jpg, which is exactly the placeholder
name the cleaned content.xhtml files reference (src="images/img_*.jpg").

Usage:
    extract_book_images.py --all [--force] [--max-px 720] [--quality 82]
    extract_book_images.py books/st-takla.org/<author>/<book> [...]

Per book it:
  1. collects every `images/<name>` referenced by the book's chapter
     content.xhtml files,
  2. pulls the matching OEBPS/images/<name> entries out of the book's .epub,
  3. resizes (only shrinks; never upscales) and writes them to <book>/images/,
  4. records any referenced image that is NOT in the epub (candidates for a
     later, bandwidth-permitting network fetch) into a missing-images report.

Prints one JSON summary line per book and a final TOT:{...} line.
"""
import argparse, glob, json, os, re, subprocess, sys, zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOKS_ROOT = os.path.join(REPO, "books", "st-takla.org")
IMG_REF_RE = re.compile(r'src="images/([^"]+)"')


def referenced_images(book_dir):
    names = set()
    for cx in glob.glob(os.path.join(book_dir, "chapters", "*", "content.xhtml")):
        try:
            with open(cx, encoding="utf-8") as fh:
                txt = fh.read()
        except OSError:
            continue
        for m in IMG_REF_RE.finditer(txt):
            names.add(m.group(1))
    return names


def resize_bytes(data, max_px, quality, out_path):
    """Shrink (never enlarge) via ImageMagick, write to out_path. Returns bytes written."""
    ext = os.path.splitext(out_path)[1].lower().lstrip(".") or "jpg"
    fmt = "jpg" if ext in ("jpg", "jpeg") else ext
    # `>` geometry flag = only resize if larger than the box.
    cmd = ["magick", "-", "-resize", f"{max_px}x{max_px}>", "-strip",
           "-quality", str(quality), f"{fmt}:-"]
    proc = subprocess.run(cmd, input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    if proc.returncode != 0 or not proc.stdout:
        # Fall back to the raw bytes so we at least have the image.
        out = data
    else:
        out = proc.stdout
    with open(out_path, "wb") as fh:
        fh.write(out)
    return len(out)


def process_book(book_dir, max_px, quality, force):
    wanted = referenced_images(book_dir)
    summary = {"book": os.path.relpath(book_dir, REPO),
               "referenced": len(wanted), "extracted": 0, "skipped": 0,
               "missing": [], "bytes": 0}
    if not wanted:
        return summary

    out_dir = os.path.join(book_dir, "images")
    os.makedirs(out_dir, exist_ok=True)

    epubs = glob.glob(os.path.join(book_dir, "*.epub"))
    # Map basename -> zip member path, across all epubs in the book.
    members = {}
    for epub in epubs:
        try:
            zf = zipfile.ZipFile(epub)
        except (zipfile.BadZipFile, OSError):
            continue
        with zf:
            for info in zf.infolist():
                base = os.path.basename(info.filename)
                if base in wanted and base not in members:
                    members[base] = (epub, info.filename)

    for name in sorted(wanted):
        out_path = os.path.join(out_dir, name)
        if os.path.exists(out_path) and not force:
            summary["skipped"] += 1
            continue
        if name not in members:
            summary["missing"].append(name)
            continue
        epub, member = members[name]
        try:
            with zipfile.ZipFile(epub) as zf:
                data = zf.read(member)
        except (KeyError, zipfile.BadZipFile, OSError):
            summary["missing"].append(name)
            continue
        try:
            summary["bytes"] += resize_bytes(data, max_px, quality, out_path)
            summary["extracted"] += 1
        except Exception as exc:  # noqa: BLE001 - keep going across the corpus
            summary["missing"].append(name)
            sys.stderr.write(f"resize failed {name}: {exc}\n")

    if summary["missing"]:
        with open(os.path.join(out_dir, "_missing.json"), "w") as fh:
            json.dump(sorted(summary["missing"]), fh)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("books", nargs="*", help="book dirs; or use --all")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--shard", help="i/n: process only shard i of n (1-based) of --all")
    ap.add_argument("--force", action="store_true", help="re-extract existing")
    ap.add_argument("--max-px", type=int, default=720)
    ap.add_argument("--quality", type=int, default=82)
    args = ap.parse_args()

    if args.all:
        book_dirs = sorted(
            d for d in glob.glob(os.path.join(BOOKS_ROOT, "*", "*"))
            if os.path.isdir(d)
        )
        if args.shard:
            i, n = (int(x) for x in args.shard.split("/"))
            book_dirs = [b for idx, b in enumerate(book_dirs) if idx % n == (i - 1)]
    else:
        book_dirs = [os.path.abspath(b) for b in args.books]

    tot = {"books": 0, "referenced": 0, "extracted": 0, "skipped": 0,
           "missing": 0, "bytes": 0}
    for bd in book_dirs:
        s = process_book(bd, args.max_px, args.quality, args.force)
        tot["books"] += 1
        for k in ("referenced", "extracted", "skipped", "bytes"):
            tot[k] += s[k]
        tot["missing"] += len(s["missing"])
        print(json.dumps(s, ensure_ascii=False), flush=True)
    print("TOT:" + json.dumps(tot), flush=True)


if __name__ == "__main__":
    main()
