# Arabic / RTL contract + verification checklist
DATA INTEGRITY (the sacred-text guards):
- PRESERVE tashkeel/diacritics (U+064B..U+0652, shadda, superscript alef) EXACTLY.
  The round-trip text diff compares WITH diacritics; an LLM "cleanup" that strips them
  is the prime failure — discard it and STOP.
- Detect & fix mojibake / Windows-1256 remnants (heuristic: unexpected CP1256/Latin-1
  byte patterns in ar text; presentation-form leakage U+FE70..U+FEFF). Fix via LLM but
  diff-gate. Normalize to canonical Arabic block + NFC.
- NEVER normalize hamza/alef/taa-marbuta in DISPLAY text (variants carry meaning);
  normalization is for the author match_key / search index ONLY.

DIRECTION / BIDI:
- dir="rtl" + lang="ar" on <html> and <body> (English: dir="ltr" lang="en").
- Wrap genuinely LTR runs (Latin names, numbers, scripture refs) in <span dir="ltr">;
  rely on the Unicode bidi algorithm — NEVER manually reorder characters.
- EPUB spine: page-progression-direction="rtl". Verify in a REAL reader
  (Readium RTL blank-page bug exists), not just a validator.

RENDERING (style.css, already in repo): line-height ~1.9 so stacked diacritics don't clip;
  tashkeel-capable font stack (Amiri / Scheherazade New / Noto Naskh Arabic).

CHECKLIST (phase 60):
[ ] tashkeel preserved (round-trip diff with diacritics ≈ 0)
[ ] no mojibake / CP1256 / presentation-form leakage
[ ] dir/lang correct on roots; LTR runs wrapped; no manual reordering
[ ] page-progression-direction=rtl (ar) / ltr (en); checked in a real reader
[ ] display text keeps original hamza/alef/taa-marbuta variants
