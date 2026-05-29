# Renderer-compatible HTML subset (the strict contract for every content.xhtml)
The SAME content.xhtml feeds the web renderer (sanitize-html + html-react-parser, no
dangerouslySetInnerHTML) AND the EPUB builder. Emit only what the sanitizer keeps.

ENVELOPE (per chapter):
  <?xml version="1.0" encoding="utf-8"?>
  <!DOCTYPE html>
  <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ar" lang="ar" dir="rtl">
  <head><meta charset="utf-8"/><title>{chapter title}</title>
  <link rel="stylesheet" type="text/css" href="style.css"/></head>
  <body dir="rtl"><h1>{chapter title}</h1> ...body... </body></html>
  (English: lang="en" dir="ltr" on both <html> and <body>.)

RENDERER BEHAVIOR TO DESIGN FOR:
- Only inner <body> is consumed. First top-level <h1> is the title and is STRIPPED
  (page chrome shows it). Every OTHER heading is DEMOTED one level (hN->h(N+1), cap h6):
  author <h2> renders as h3. So: ONE <h1> title, then use <h2>/<h3> for sections.

ALLOWED TAGS (everything else discarded; font/center/div unwrapped, children kept):
  p br hr h1 h2 h3 h4 h5 h6 strong b em i u sup sub a span img
  ul ol li table thead tbody tr td th blockquote
  (b->strong, i->em on transform.)

ALLOWED ATTRIBUTES (all others stripped — class/style/width/align/color/face are useless):
  a:[href,id]   img:[src,alt]   td:[colspan,rowspan]   th:[colspan,rowspan]   *:[dir,lang]
SCHEMES: http https mailto ; relative + #fragment kept.

IMAGES: relative ONLY. src MUST match ^(?:\./)?images/<file>$ where
  file = img_<md5(remote_url)[:12]>.<ext>  (jpg|jpeg|png|gif|webp).
  Any remote/data/empty <img> is DROPPED. Always include non-empty alt.
  Image-wrapper table (<table><tr><td><a href=gallery><img/></a></td></tr>
  <tr><td><div><p>caption</p></div></td></tr></table>) -> ContentFigure.

FOOTNOTES (keep these exact shapes so the renderer pairs them):
  in-body marker: <sup><b><a href="#(1)">(1)</a></b></sup>
  note block:     <a href="#1">(1)</a> ... under <h6><a>الحواشي والمراجع</a></h6> + "_____"
  The renderer collapses _ftnN/_ftnhrefN keys and re-attaches ids; preserve marker text.

CROSS-REFS: in-library st-takla URLs (absolute or ../..) are rewritten to internal routes;
  external kept; unresolved #anchor kept as a graceful dead link. Never delete visible text.

TOC TABLE: a table containing محتويات/Contents + intra-page # anchors -> ChapterToc.

FORBIDDEN: inline styles, classes, font/center, script/style/iframe/nav/form/input,
  on*=, javascript:, presentational attributes, non-images/* <img>.
