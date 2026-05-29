#!/usr/bin/env python3
"""
state.py — shared helpers for the LLM-driven publishing pipeline (PLAN §3a, §11).

Deterministic plumbing used by every pipeline tool:
  * atomic writes (write a temp file, then os.replace — no half-written outputs),
  * content hashing (sha256 of bytes/text/files; per-book source_hash),
  * the per-book build-state file books/.../<book>/.build/state.json
    (Appendix C schema), with hash-gated phase status and a review queue,
  * small conveniences: book_id derivation, chapter/content enumeration,
    issue accumulation, ISO timestamps.

The state file is written by scripts and read by the agent for decisions. It is
pipeline scratch under `.build/` and is NOT consumed by the web app.

This module has no third-party dependencies and no network access.
"""
import os
import re
import glob
import json
import hashlib
import tempfile
import datetime

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)

SCHEMA_VERSION = 1


# ------------------------------- time ----------------------------------
def now_iso():
    """UTC timestamp, second precision, e.g. 2026-05-29T12:34:56Z."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------- atomic writes ------------------------------
def atomic_write_bytes(path, data):
    """Write bytes to `path` atomically (temp file in the same dir + os.replace)."""
    path = os.path.abspath(path)
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=os.path.basename(path))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_text(path, text):
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path, obj):
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


# ------------------------------ hashing ---------------------------------
def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_text(text):
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_files(paths):
    """Stable hash over an ordered list of files: sha256 of
    "<relbasename>\\n<filehash>\\n" lines (missing files contribute "missing")."""
    h = hashlib.sha256()
    for p in paths:
        key = os.path.basename(os.path.dirname(p)) + "/" + os.path.basename(p)
        try:
            fh = sha256_file(p)
        except OSError:
            fh = "missing"
        h.update((key + "\n" + fh + "\n").encode("utf-8"))
    return h.hexdigest()


# ----------------------------- book paths -------------------------------
def book_id_from_dir(book_dir):
    """books/st-takla.org/<author>/<book>  ->  "st-takla.org/<author>/<book>"."""
    parts = os.path.normpath(os.path.abspath(book_dir)).split(os.sep)
    try:
        i = len(parts) - 1 - parts[::-1].index("books")
    except ValueError:
        # Not under a 'books' root — fall back to the last three segments.
        return "/".join(parts[-3:])
    return "/".join(parts[i + 1:])


def book_slug(book_dir):
    return os.path.basename(os.path.normpath(os.path.abspath(book_dir)))


def author_slug(book_dir):
    return os.path.basename(os.path.dirname(os.path.normpath(os.path.abspath(book_dir))))


def dest_relpath(book_dir):
    """Catalog `dest`: path relative to the repo root, posix-style."""
    rel = os.path.relpath(os.path.abspath(book_dir), REPO)
    return rel.replace(os.sep, "/")


def chapter_dirs(book_dir):
    """Ordered list of chapters/<NN-slug>/ directories (sorted by NN prefix)."""
    dirs = [d for d in glob.glob(os.path.join(book_dir, "chapters", "*"))
            if os.path.isdir(d)]
    return sorted(dirs, key=lambda d: os.path.basename(d))


def content_paths(book_dir):
    """Ordered list of chapters/<NN-slug>/content.xhtml that exist on disk."""
    out = []
    for d in chapter_dirs(book_dir):
        p = os.path.join(d, "content.xhtml")
        if os.path.exists(p):
            out.append(p)
    return out


def manifest_path(book_dir):
    return os.path.join(book_dir, "manifest.json")


def meta_path(book_dir):
    return os.path.join(book_dir, "meta.json")


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def content_chapter_count(book_dir):
    """Number of content chapters = non-index manifest entries == chapter dirs.
    Used to keep catalog.chapter_links_guess consistent (PLAN §0.2)."""
    return len(chapter_dirs(book_dir))


def compute_source_hash(book_dir):
    """sha256 over manifest.json + every chapters/*/content.xhtml (PLAN §3a)."""
    paths = [manifest_path(book_dir)] + content_paths(book_dir)
    return hash_files(paths)


# ------------------------------ state -----------------------------------
def build_dir(book_dir):
    return os.path.join(book_dir, ".build")


def state_path(book_dir):
    return os.path.join(build_dir(book_dir), "state.json")


def default_state(book_dir, phase="html"):
    return {
        "book_id": book_id_from_dir(book_dir),
        "schema_version": SCHEMA_VERSION,
        "phase": phase,
        "source_hash": "",
        "phases": {},
        "issues": [],
        "review": "pending",
    }


def load_state(book_dir):
    return load_json(state_path(book_dir), None)


def save_state(book_dir, state):
    atomic_write_json(state_path(book_dir), state)


def init_state(book_dir, phase="html"):
    """Load the existing state or create a fresh one; always refresh source_hash
    and book_id (idempotent)."""
    state = load_state(book_dir) or default_state(book_dir, phase)
    state.setdefault("phases", {})
    state.setdefault("issues", [])
    state.setdefault("review", "pending")
    state["book_id"] = book_id_from_dir(book_dir)
    state["schema_version"] = SCHEMA_VERSION
    state["source_hash"] = compute_source_hash(book_dir)
    return state


# ------------------------- phase hash-gating ----------------------------
def phase_record(state, name):
    return state.setdefault("phases", {}).get(name, {})


def phase_is_current(state, name, input_hash):
    """True iff phase `name` is done and was last run on the same input_hash —
    i.e. it can be skipped (PLAN §3a idempotency rule 1)."""
    rec = phase_record(state, name)
    return rec.get("status") == "done" and rec.get("input_hash") == input_hash


def set_phase(state, name, status, input_hash=None):
    rec = state.setdefault("phases", {}).setdefault(name, {})
    rec["status"] = status
    if input_hash is not None:
        rec["input_hash"] = input_hash
    rec["ts"] = now_iso()
    return rec


# ------------------------------ issues ----------------------------------
def add_issue(state, severity, code, detail, chapter=None):
    """Append an issue (info|warn|error) to the review queue, de-duplicating on
    (severity, code, detail, chapter)."""
    assert severity in ("info", "warn", "error"), severity
    issues = state.setdefault("issues", [])
    issue = {"severity": severity, "code": code, "detail": detail}
    if chapter:
        issue["chapter"] = chapter
    if issue not in issues:
        issues.append(issue)
    return issue


def clear_issues(state, code=None):
    """Drop all issues (or only those with a given code) so a re-run rebuilds
    them from source rather than appending duplicates (PLAN §2 rebuild-don't-append)."""
    if code is None:
        state["issues"] = []
    else:
        state["issues"] = [i for i in state.get("issues", []) if i.get("code") != code]


def issues_by_severity(state, severity):
    return [i for i in state.get("issues", []) if i.get("severity") == severity]


# --------------------------- arabic helpers -----------------------------
# Diacritics that MUST be preserved through every text transform (tashkeel,
# shadda, superscript alef, tatweel handled separately). The round-trip text
# diff (PLAN §10 check 4) compares WITH these.
TASHKEEL = "ًٌٍَُِّْٰٕٓٔ"
_WS_RE = re.compile(r"\s+")


def normalize_for_diff(text):
    """Collapse whitespace but KEEP Arabic diacritics — the sacred-text guard.
    Used by both sides of the round-trip diff so only genuine content loss trips
    it (PLAN §2, §10)."""
    return _WS_RE.sub(" ", text or "").strip()


if __name__ == "__main__":
    # tiny self-test / round-trip smoke check
    import sys
    import tempfile as _tf
    d = _tf.mkdtemp()
    p = os.path.join(d, "x.json")
    atomic_write_json(p, {"a": 1, "ar": "أكلت بإرادتي"})
    assert load_json(p)["ar"] == "أكلت بإرادتي"
    assert sha256_text("abc") == sha256_bytes(b"abc")
    print("state.py self-test OK ->", p, file=sys.stderr)
