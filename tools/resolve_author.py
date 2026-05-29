#!/usr/bin/env python3
"""
resolve_author.py — PLAN §6 / phase 45.

extract -> normalize -> research -> dedup (tiers) -> idempotent upsert -> link.

Deterministic except the surface-form extraction (LLM, supplied via --extraction
or defaulted from meta.author) and optional bio drafting. Given a book dir it:
  1. takes the primary contributor surface form (LLM extraction JSON if given,
     else meta.author);
  2. computes the AR (+EN) `match_key` (§6.2) — the dedup key, not display;
  3. optionally researches authority records (Wikidata; best-effort, descriptive
     User-Agent) unless --no-network;
  4. dedups against authors/*/info.json by tiers:
       Tier 0  authority QID exact            -> auto-link
       Tier 1  normalized match_key exact     -> auto-link
       Tier 2  fuzzy >= 92 (+year agrees)     -> auto-link
               82..92                          -> queue for review (NO write)
               < 82                            -> auto-create
  5. upserts authors/<slug>/info.json (create-if-absent / merge-not-clobber;
     union aliases; resolution provenance; sticky method:"manual");
  6. links meta.json.author_slug AND tools/catalog.json[book].author_slug;
  7. records state.author and appends tools/author-review-queue.json when needed.

rapidfuzz is preferred; a pure-Python fallback (token_set_ratio + Jaro-Winkler)
keeps the tool runnable when rapidfuzz is not installed.

Usage:
  python3 tools/resolve_author.py <book-dir> [--no-network] [--extraction FILE]
                                  [--authors-dir DIR] [--dry-run]
"""
import os
import re
import sys
import json
import unicodedata
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state as st
from extract_book import CATALOG, REPO

# ----------------------------- fuzzy matcher ----------------------------
try:
    from rapidfuzz import fuzz as _rf
    def token_set_ratio(a, b):
        return _rf.token_set_ratio(a, b)
    def jaro_winkler(a, b):
        from rapidfuzz.distance import JaroWinkler
        return JaroWinkler.normalized_similarity(a, b)
    FUZZ_BACKEND = "rapidfuzz"
except Exception:  # pragma: no cover - environment without rapidfuzz
    def token_set_ratio(a, b):
        ta, tb = set(a.split()), set(b.split())
        if not ta or not tb:
            return 0.0
        inter = ta & tb
        return 100.0 * (2 * len(inter)) / (len(ta) + len(tb))
    def jaro_winkler(a, b):
        # Jaro
        if a == b:
            return 1.0
        if not a or not b:
            return 0.0
        md = max(len(a), len(b)) // 2 - 1
        ma = [False] * len(a); mb = [False] * len(b); m = 0
        for i, ca in enumerate(a):
            for j in range(max(0, i - md), min(len(b), i + md + 1)):
                if not mb[j] and b[j] == ca:
                    ma[i] = mb[j] = True; m += 1; break
        if m == 0:
            return 0.0
        sa = "".join(a[i] for i in range(len(a)) if ma[i])
        sb = "".join(b[j] for j in range(len(b)) if mb[j])
        t = sum(1 for x, y in zip(sa, sb) if x != y) / 2
        jaro = (m / len(a) + m / len(b) + (m - t) / m) / 3
        pfx = 0
        for x, y in zip(a, b):
            if x == y and pfx < 4:
                pfx += 1
            else:
                break
        return jaro + pfx * 0.1 * (1 - jaro)
    FUZZ_BACKEND = "fallback"


# ------------------------------- match_key ------------------------------
AR_HONORIFICS = {"قداسة", "البابا", "بابا", "الانبا", "انبا", "نيافة", "الاسقف",
                 "اسقف", "المطران", "مطران", "القمص", "قمص", "القس", "الاب",
                 "ابونا", "الراهب", "القديس", "قديس", "مار", "الشماس", "دكتور",
                 "د", "ا", "است", "الاستاذ"}
AR_ORDINALS = {"اول": "1", "الاول": "1", "ثاني": "2", "ثالث": "3", "رابع": "4",
               "خامس": "5", "سادس": "6", "سابع": "7", "ثامن": "8", "تاسع": "9",
               "عاشر": "10"}
EN_HONORIFICS = {"hh", "hg", "st", "saint", "pope", "bishop", "metropolitan",
                 "anba", "abba", "abouna", "father", "fr", "hegumen", "qommos",
                 "mar", "mr", "dr", "prof", "rev", "the", "of"}
EN_SYNONYMS = {"shenoute": "shenouda", "kyrillos": "cyril", "bishoy": "pishoy",
               "athanasios": "athanasius", "boulos": "paul", "boles": "paul",
               "youhanna": "john"}
EN_REGNAL = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6"}


def _fold_ar(s):
    """The character-level Arabic folding shared by normalize_ar and the
    honorific/ordinal tables (so e.g. 'قداسة' -> 'قداسه' matches the set)."""
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[ً-ْٰـ]", "", s)            # tashkeel + tatweel
    s = re.sub(r"[إأآا]", "ا", s)
    s = s.replace("ة", "ه").replace("ى", "ي")
    s = re.sub(r"[ؤئء]", "", s)
    return s


# Canonicalize the honorific/ordinal tables with the SAME folding + leading
# article strip applied to tokens at compare time.
AR_HONORIFICS_NORM = {re.sub(r"^ال", "", _fold_ar(h)) for h in AR_HONORIFICS}
AR_ORDINALS_NORM = {re.sub(r"^ال", "", _fold_ar(k)): v for k, v in AR_ORDINALS.items()}


def normalize_ar(s):
    s = _fold_ar(s)
    s = re.sub(r"\bال", "", s)               # leading definite article
    toks = []
    for t in s.split():
        if not t or t in AR_HONORIFICS_NORM:
            continue
        toks.append(AR_ORDINALS_NORM.get(t, t))
    return " ".join(toks).strip()


def normalize_en(s):
    s = unicodedata.normalize("NFKC", s or "")
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    toks = []
    for t in s.split():
        if t in EN_HONORIFICS:
            continue
        t = EN_SYNONYMS.get(t, t)
        t = EN_REGNAL.get(t, t)
        toks.append(t)
    return " ".join(toks).strip()


def match_keys(name_ar, name_en=None):
    keys = []
    ka = normalize_ar(name_ar) if name_ar else ""
    if ka:
        keys.append(ka)
    ke = normalize_en(name_en) if name_en else ""
    if ke:
        keys.append(ke)
    return keys


def slugify_en(name_en, name_ar):
    base = normalize_en(name_en) if name_en else ""
    if not base:
        # fall back to a transliteration-free ascii of nothing -> use a hash tag
        base = "author-" + st.sha256_text(name_ar or "x")[:8]
    return re.sub(r"\s+", "-", base).strip("-")


# ------------------------------ research --------------------------------
UA = {"User-Agent": "CopticLibrary/1.0 author-resolver (+book archival; contact athanasius742)"}


def wikidata_lookup(term):
    """Best-effort Wikidata search -> {qid, name_ar, name_en, birth, death,
    wikipedia_ar, wikipedia_en} or None. Network; descriptive UA."""
    import urllib.request
    import urllib.parse
    try:
        q = urllib.parse.urlencode({"action": "wbsearchentities", "search": term,
                                    "language": "ar", "format": "json", "limit": 1})
        url = "https://www.wikidata.org/w/api.php?" + q
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
        hits = data.get("search", [])
        if not hits:
            return None
        qid = hits[0]["id"]
        ent_url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
        req = urllib.request.Request(ent_url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            ed = json.load(r)
        ent = ed["entities"][qid]
        labels = ent.get("labels", {})
        claims = ent.get("claims", {})
        def year(pid):
            try:
                t = claims[pid][0]["mainsnak"]["datavalue"]["value"]["time"]
                m = re.match(r"[+\-](\d{4})", t)
                return int(m.group(1)) if m else None
            except Exception:
                return None
        sitelinks = ent.get("sitelinks", {})
        def wiki(lang):
            sl = sitelinks.get(f"{lang}wiki")
            if not sl:
                return None
            return f"https://{lang}.wikipedia.org/wiki/" + sl["title"].replace(" ", "_")
        return {"qid": qid,
                "name_ar": labels.get("ar", {}).get("value"),
                "name_en": labels.get("en", {}).get("value"),
                "birth_year": year("P569"), "death_year": year("P570"),
                "wikipedia_ar": wiki("ar"), "wikipedia_en": wiki("en")}
    except Exception as e:
        print(f"  wikidata lookup failed: {e}", file=sys.stderr)
        return None


# ------------------------------ dedup -----------------------------------
def load_author_index(authors_dir):
    """Return list of {slug, info, keys, qid, birth, death} over authors/*/."""
    out = []
    if not os.path.isdir(authors_dir):
        return out
    for slug in sorted(os.listdir(authors_dir)):
        info = st.load_json(os.path.join(authors_dir, slug, "info.json"))
        if not info:
            continue
        keys = set(info.get("match_key") or [])
        if not keys:
            keys = set(match_keys(info.get("name_ar"), info.get("name_en")))
        out.append({"slug": slug, "info": info, "keys": keys,
                    "qid": (info.get("authority") or {}).get("wikidata"),
                    "birth": info.get("birth_year"), "death": info.get("death_year")})
    return out


def best_fuzzy(my_keys, my_name_ar, my_name_en, index):
    best = (0.0, None)
    for entry in index:
        cand_strs = list(entry["keys"]) + [normalize_ar(entry["info"].get("name_ar") or ""),
                                           normalize_en(entry["info"].get("name_en") or "")]
        for mk in (list(my_keys) + [normalize_ar(my_name_ar or ""), normalize_en(my_name_en or "")]):
            if not mk:
                continue
            for cs in cand_strs:
                if not cs:
                    continue
                # same-script comparisons only (AR vs AR, EN vs EN)
                if bool(re.search(r"[a-z]", mk)) != bool(re.search(r"[a-z]", cs)):
                    continue
                score = max(token_set_ratio(mk, cs), jaro_winkler(mk, cs) * 100.0)
                if score > best[0]:
                    best = (score, entry)
    return best


def years_agree(a, b):
    if a is None or b is None:
        return None
    return abs(a - b) <= 1


# ------------------------------ upsert ----------------------------------
def follow_alias(slug, authors_dir, depth=0):
    if depth > 3:
        return slug
    info = st.load_json(os.path.join(authors_dir, slug, "info.json"))
    if info and info.get("kind") == "alias" and info.get("aliases_to"):
        return follow_alias(info["aliases_to"], authors_dir, depth + 1)
    return slug


def upsert_author(slug, authors_dir, surface, keys, research, method, confidence,
                  matched_slug, needs_review, dry_run):
    path = os.path.join(authors_dir, slug, "info.json")
    existing = st.load_json(path)
    resolution = {"confidence": round(confidence, 4), "method": method,
                  "matched_slug": matched_slug, "source_surface": surface,
                  "reviewed": False, "needs_review": needs_review, "ts": st.now_iso()}
    if existing is None:
        info = {
            "slug": slug, "kind": "person",
            "name_ar": (research or {}).get("name_ar") or surface,
            "name_en": (research or {}).get("name_en") or "",
            "bio_ar": None, "bio_en": None, "bio_source": None,
            "birth_year": (research or {}).get("birth_year"),
            "death_year": (research or {}).get("death_year"),
            "portrait": None, "portrait_source": None,
            "portrait_status": "missing", "portrait_license": None,
            "wikipedia_ar": (research or {}).get("wikipedia_ar"),
            "wikipedia_en": (research or {}).get("wikipedia_en"),
            "aliases_to": None,
            "match_key": sorted(set(keys)),
            "aliases_ar": [], "aliases_en": [],
            "authority": {"wikidata": (research or {}).get("qid"), "viaf": None, "loc": None},
            "resolution": resolution,
        }
        action = "created"
    else:
        info = dict(existing)
        # sticky manual: never override a human-resolved record
        prev_method = (existing.get("resolution") or {}).get("method")
        if prev_method == "manual":
            method = "manual"
            resolution["method"] = "manual"
        # union match keys
        info["match_key"] = sorted(set(existing.get("match_key") or []) | set(keys))
        # fill null fields only (merge-not-clobber)
        for k in ("name_en", "bio_ar", "bio_en", "birth_year", "death_year",
                  "wikipedia_ar", "wikipedia_en"):
            if not info.get(k) and research and research.get(k):
                info[k] = research[k]
        auth = info.setdefault("authority", {"wikidata": None, "viaf": None, "loc": None})
        if research and research.get("qid") and not auth.get("wikidata"):
            auth["wikidata"] = research["qid"]
        info.setdefault("aliases_ar", [])
        info.setdefault("aliases_en", [])
        if prev_method != "manual":
            info["resolution"] = resolution
        action = "merged"
    if not dry_run:
        st.atomic_write_json(path, info)
    return action, info


# ------------------------------ main ------------------------------------
def resolve(book_dir, authors_dir, no_network, extraction, dry_run):
    meta = st.load_json(st.meta_path(book_dir))
    if not meta:
        raise SystemExit("resolve_author: meta.json missing")
    # primary contributor surface form
    surface = meta.get("author") or ""
    name_en_hint = meta.get("author_en") or ""
    if extraction:
        ex = st.load_json(extraction) or {}
        prims = [c for c in ex.get("contributors", [])
                 if c.get("role") in ("author", "compiler", "translator")]
        prims.sort(key=lambda c: -float(c.get("confidence", 0)))
        if prims:
            surface = prims[0].get("surface_form") or surface
            if prims[0].get("lang") == "en":
                name_en_hint = surface

    keys = match_keys(surface, name_en_hint)
    research = None
    if not no_network:
        research = wikidata_lookup(surface)

    index = load_author_index(authors_dir)
    # current slug hint from the book's existing link
    slug_hint = meta.get("author_slug") or st.author_slug(book_dir)

    matched_slug = None
    method = "created"
    confidence = 0.5
    needs_review = False

    # Tier 0 — authority QID exact
    qid = (research or {}).get("qid")
    if qid:
        for e in index:
            if e["qid"] and e["qid"] == qid:
                matched_slug, method, confidence = e["slug"], "qid", 0.99
                break
    # Tier 1 — normalized match_key exact
    if matched_slug is None:
        keyset = set(keys)
        for e in index:
            if keyset & e["keys"]:
                matched_slug, method, confidence = e["slug"], "matchkey", 0.97
                break
    # Tier 2 — fuzzy
    if matched_slug is None and index:
        score, e = best_fuzzy(keys, surface, name_en_hint, index)
        if e is not None:
            ya = years_agree((research or {}).get("birth_year") or (research or {}).get("death_year"),
                             e["death"] or e["birth"])
            if score >= 92 and ya is not False:
                matched_slug, method, confidence = e["slug"], "fuzzy", score / 100.0
            elif 82 <= score < 92:
                matched_slug, method, confidence = None, "review", score / 100.0
                needs_review = True
                review_candidate = e["slug"]

    if matched_slug is None and not needs_review:
        # auto-create — prefer the book's existing slug to stay stable/linked
        matched_slug = slug_hint or slugify_en(name_en_hint, surface)
        method = "created"
        confidence = max(confidence, 0.6)

    result = {"surface": surface, "keys": keys, "research": research,
              "needs_review": needs_review, "method": method,
              "confidence": confidence}

    if needs_review:
        # queue for human review; NO write, keep existing link as-is
        queue_path = os.path.join(REPO, "tools", "author-review-queue.json")
        queue = st.load_json(queue_path, [])
        entry = {"book_id": st.book_id_from_dir(book_dir), "surface_form": surface,
                 "match_keys": keys, "proposed_match": locals().get("review_candidate"),
                 "score": round(confidence * 100, 1), "ts": st.now_iso()}
        if entry not in queue:
            queue.append(entry)
        if not dry_run:
            st.atomic_write_json(queue_path, queue)
        result["slug"] = slug_hint
        result["action"] = "review-queued"
        return result

    # resolve aliases to terminal slug so links never point at a dup
    terminal = follow_alias(matched_slug, authors_dir)
    action, info = upsert_author(terminal, authors_dir, surface, keys, research,
                                 method, confidence, matched_slug, needs_review, dry_run)
    # link meta + catalog
    if not dry_run:
        if meta.get("author_slug") != terminal:
            meta["author_slug"] = terminal
            st.atomic_write_json(st.meta_path(book_dir), meta)
        recs = st.load_json(CATALOG, [])
        bid = st.book_id_from_dir(book_dir)
        for r in recs:
            if r.get("book_id") == bid:
                r["author_slug"] = terminal
        st.atomic_write_json(CATALOG, recs)
    result["slug"] = terminal
    result["action"] = action
    return result


def main():
    ap = argparse.ArgumentParser(description="Resolve, dedup, and link a book's author (§6).")
    ap.add_argument("book_dir")
    ap.add_argument("--no-network", action="store_true", help="skip authority research")
    ap.add_argument("--extraction", help="LLM author-extraction JSON")
    ap.add_argument("--authors-dir", default=os.path.join(REPO, "authors"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    book_dir = os.path.abspath(args.book_dir)

    r = resolve(book_dir, os.path.abspath(args.authors_dir), args.no_network,
                args.extraction, args.dry_run)
    print(f"resolve_author: {r['action']} slug='{r.get('slug')}' method={r['method']} "
          f"confidence={r['confidence']:.2f} needs_review={r['needs_review']} "
          f"(fuzz={FUZZ_BACKEND})")

    state = st.load_state(book_dir)
    if state is not None and not args.dry_run:
        state["author"] = {"slug": r.get("slug"), "confidence": r["confidence"],
                           "method": r["method"], "needs_review": r["needs_review"],
                           "authority": {"wikidata": (r["research"] or {}).get("qid")} if r["research"] else {},
                           "source_surface": r["surface"]}
        st.clear_issues(state, "author-confidence")
        if r["confidence"] < 0.6 and not r["needs_review"]:
            st.add_issue(state, "error", "author-confidence",
                         f"primary author confidence {r['confidence']:.2f} < 0.6")
        st.set_phase(state, "author", "done", st.compute_source_hash(book_dir))
        st.save_state(book_dir, state)


if __name__ == "__main__":
    main()
