#!/usr/bin/env python3
"""
reattribute_source.py — PLAN §4.1a / phase 15.

St-Takla editors inserted first-person "we / our site" asides that, re-hosted
here, wrongly imply THIS library is st-takla or speaks in its voice (e.g.
"وقد تكلمنا عن هذا الموضوع في موقع الأنبا تكلاهيمانوت"). This step rewrites such
asides to refer to st-takla as a SEPARATE, EXTERNAL website (neutral
third-person attribution) WITHOUT deleting the author's content. It is the one
sanctioned exception to the verbatim/round-trip rule — surgical, span-bounded,
and change-logged.

Owner split (PLAN §2): CODE does deterministic candidate detection and applies
rewrites with span-bounded safety + a change log; the LLM supplies the minimal
in-span rewrite text. This tool therefore has two modes:

  default          — scan every chapter for self-reference candidates (a
                     st-takla marker COMBINED WITH first-person/our-site
                     framing) and record them in state.source_reattribution
                     .pending_review for human/LLM review. Conservative: nothing
                     is rewritten automatically (ambiguous voice is never guessed).
  --apply FILE     — apply LLM-provided rewrites. FILE is a JSON list of
                     {chapter, before, after, reason}. Each `before` MUST occur
                     EXACTLY ONCE in that chapter's content.xhtml; the edit is a
                     single span-bounded replacement (everything outside the span
                     stays byte-identical, tashkeel intact). Any rewrite that
                     can't be matched uniquely is rejected and logged — never
                     applied. Applied rewrites are recorded in
                     state.source_reattribution.rewrites for the §10 human gate.

Usage:
  python3 tools/reattribute_source.py <book-dir>
  python3 tools/reattribute_source.py <book-dir> --apply rewrites.json
"""
import os
import re
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state as st

# St-Takla self-reference MARKERS (the site naming itself).
MARKERS = [
    "موقع الأنبا تكلا", "الأنبا تكلاهيمانوت", "تكلاهيمانوت", "موقعنا",
    "st-takla", "st takla",
]
# FIRST-PERSON / "our-site" FRAMING that turns a marker into an editorial aside.
FRAMING = [
    "تكلمنا", "ذكرنا", "نشرنا", "على موقعنا", "في موقعنا", "موقعنا",
    "أضفنا", "وضعنا", "قمنا", "لنا في موقع",
]
TAG_RE = re.compile(r"<[^>]+>")
WINDOW = 90  # chars of context on each side of a framing hit


def _text_only(xhtml):
    body = re.search(r"<body[^>]*>([\s\S]*?)</body>", xhtml, re.I)
    s = body.group(1) if body else xhtml
    s = TAG_RE.sub(" ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&")
         .replace("&lt;", "<").replace("&gt;", ">"))
    s = re.sub(r"&[a-zA-Z#0-9]+;", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _has_marker(window):
    low = window.lower()
    return any(m.lower() in low for m in MARKERS)


def scan_chapter(text):
    """Return candidate context windows where framing + a marker co-occur."""
    candidates = []
    low = text.lower()
    for fr in FRAMING:
        start = 0
        frl = fr.lower()
        while True:
            i = low.find(frl, start)
            if i < 0:
                break
            start = i + len(fr)
            a = max(0, i - WINDOW)
            b = min(len(text), i + len(fr) + WINDOW)
            window = text[a:b]
            if _has_marker(window):
                ctx = re.sub(r"\s+", " ", window).strip()
                if ctx not in candidates:
                    candidates.append(ctx)
    return candidates


def do_scan(book_dir):
    pending = []
    for cx in st.content_paths(book_dir):
        slug = re.sub(r"^\d+-", "", os.path.basename(os.path.dirname(cx)))
        text = _text_only(open(cx, encoding="utf-8").read())
        for ctx in scan_chapter(text):
            pending.append({"chapter": slug, "context": ctx,
                            "note": "first-person st-takla self-reference — review: rewrite to "
                                    "neutral 3rd-person external attribution or keep as-is"})
    return pending


def do_apply(book_dir, rewrites_file, state):
    rewrites = st.load_json(rewrites_file)
    if not isinstance(rewrites, list):
        raise SystemExit("--apply file must be a JSON list of {chapter, before, after, reason}")
    applied, rejected = [], []
    # map chapter slug -> content.xhtml path
    by_slug = {re.sub(r"^\d+-", "", os.path.basename(os.path.dirname(p))): p
               for p in st.content_paths(book_dir)}
    for rw in rewrites:
        ch = rw.get("chapter")
        before, after = rw.get("before"), rw.get("after")
        path = by_slug.get(ch)
        if not path or before is None or after is None:
            rejected.append({**rw, "reason_rejected": "missing chapter/before/after"})
            continue
        raw = open(path, encoding="utf-8").read()
        count = raw.count(before)
        if count != 1:
            rejected.append({**rw, "reason_rejected": f"`before` matched {count} times (need exactly 1)"})
            continue
        new = raw.replace(before, after, 1)
        # span-bounded guarantee: everything outside the single replaced span is
        # byte-identical (true by construction for a unique single replace).
        # Sanity: the only delta is before->after.
        if new.replace(after, before, 1) != raw:
            rejected.append({**rw, "reason_rejected": "replacement not span-bounded"})
            continue
        st.atomic_write_text(path, new)
        applied.append({"chapter": ch, "before": before, "after": after,
                        "reason": rw.get("reason", "")})
    return applied, rejected


def main():
    ap = argparse.ArgumentParser(description="Detect/apply st-takla self-reference re-attribution (§4.1a).")
    ap.add_argument("book_dir")
    ap.add_argument("--apply", metavar="FILE", help="JSON list of LLM rewrites to apply")
    args = ap.parse_args()
    book_dir = os.path.abspath(args.book_dir)

    state = st.init_state(book_dir, phase="html")
    sr = state.setdefault("source_reattribution",
                          {"count": 0, "rewrites": [], "pending_review": []})

    if args.apply:
        applied, rejected = do_apply(book_dir, args.apply, state)
        sr["rewrites"] = (sr.get("rewrites") or []) + applied
        st.clear_issues(state, "reattribution-rejected")
        for rj in rejected:
            st.add_issue(state, "warn", "reattribution-rejected",
                         f"{rj.get('reason_rejected')}: {str(rj.get('before',''))[:80]}",
                         rj.get("chapter"))
        # drop any pending candidate now satisfied by a rewrite
        print(f"reattribute_source: applied {len(applied)} rewrite(s), rejected {len(rejected)}")
    else:
        pending = do_scan(book_dir)
        sr["pending_review"] = pending
        st.clear_issues(state, "reattribution-pending")
        for p in pending:
            st.add_issue(state, "warn", "reattribution-pending",
                         "self-reference candidate awaits review", p["chapter"])
        print(f"reattribute_source: {len(pending)} self-reference candidate(s) flagged for review")

    sr["count"] = len(sr.get("rewrites", [])) + len(sr.get("pending_review", []))
    state["source_hash"] = st.compute_source_hash(book_dir)
    st.set_phase(state, "reattribute", "done", st.compute_source_hash(book_dir))
    st.save_state(book_dir, state)


if __name__ == "__main__":
    main()
