# PHASE 45 — Author extraction, research, dedup, idempotent link
PRECONDITIONS: meta.json present; rapidfuzz installed.
STEP 1 EXTRACT (LLM, strict JSON -> prompts/lib/schemas/author-extraction.schema.json):
  feed catalog.json.title_guess + meta.author + (Phase2: title page/colophon).
  Verbatim surface forms; explicit roles; is_collection/attribution flags; confidence.
STEP 2..5 (deterministic): python3 tools/resolve_author.py <BOOK_DIR>
  - match_key (AR+EN, §6.2 recipe);
  - research: Wikidata wbsearchentities(ar) + EntityData; VIAF AutoSuggest (REAL browser
    User-Agent — VIAF 403s bots); LC suggest/didyoumean; Wikipedia REST via sitelink title;
    st-takla /books/<slug>/; fallback thin record;
  - dedup tiers: Tier0 authority-QID -> link; Tier1 match_key== -> link;
    Tier2 RapidFuzz token_set_ratio>=92 or JaroWinkler>=0.93 (+year) -> link;
    82..92 -> append tools/author-review-queue.json, NO write; <82 -> create_author;
  - follow aliases_to to terminal slug; collections -> kind:"collection";
  - upsert authors/<slug>/info.json (create-if-absent / merge-not-clobber; union aliases;
    write resolution{confidence,method,reviewed,needs_review,ts}); honor sticky method:"manual";
  - set meta.json.author_slug AND catalog.json[book].author_slug.
SELF-CHECK: idempotent re-run = no-op; primary confidence<0.6 -> STOP (review).
OUTPUT: authors/<slug>/info.json (+portrait.jpg); state.author; review queue if needed.
