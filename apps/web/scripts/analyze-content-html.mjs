#!/usr/bin/env node
/**
 * Phase 1 corpus analysis (PLAN-content-renderers.md).
 *
 * Walks every books/st-takla.org/<author>/<book>/chapters/NN-slug/content.xhtml,
 * streaming one file at a time (never loads the whole corpus into memory), and
 * builds a machine-readable tag/attribute/structure inventory using a real HTML
 * parser (htmlparser2) — not regex.
 *
 * Outputs:
 *   apps/web/analysis/tag-inventory.json   (machine-readable)
 *
 * The companion FINDINGS.md is generated from this JSON by the operator.
 *
 * Run:  node apps/web/scripts/analyze-content-html.mjs
 */

import { promises as fs } from "node:fs";
import { createReadStream } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Parser } from "htmlparser2";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..", "..", ".."); // apps/web/scripts -> repo root
const CORPUS_ROOT = path.join(REPO_ROOT, "books", "st-takla.org");
const OUT_DIR = path.join(REPO_ROOT, "apps", "web", "analysis");
const OUT_JSON = path.join(OUT_DIR, "tag-inventory.json");

// Caps to keep the inventory bounded.
const MAX_ATTR_NAMES = 50;
const MAX_CLASS_VALUES = 80;
const MAX_ID_VALUES = 80;
const MAX_EXAMPLES_PER_TAG = 3;
const MAX_EXAMPLES_PER_STRUCT = 4;
const SNIPPET_LEN = 220;

/** Identify the "book" a file belongs to: the dir that holds the chapters/ dir. */
function bookKeyForFile(absFile) {
  const rel = path.relative(CORPUS_ROOT, absFile); // <author>/<book>/chapters/NN-slug/content.xhtml
  const parts = rel.split(path.sep);
  const idx = parts.indexOf("chapters");
  if (idx >= 1) return parts.slice(0, idx).join("/");
  return parts.slice(0, 2).join("/");
}

/** Recursively find all content.xhtml under chapters/, yielding one path at a time. */
async function* walkContentFiles(dir) {
  let entries;
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const ent of entries) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) {
      yield* walkContentFiles(full);
    } else if (ent.isFile() && ent.name === "content.xhtml") {
      if (full.includes(`${path.sep}chapters${path.sep}`)) yield full;
    }
  }
}

function readFileText(absFile) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    const stream = createReadStream(absFile, { encoding: "utf8" });
    stream.on("data", (c) => chunks.push(c));
    stream.on("end", () => resolve(chunks.join("")));
    stream.on("error", reject);
  });
}

// ---------- aggregate state ----------
/** tag -> { count, books:Set, attrNames:Map(name->count), classVals:Map, idVals:Map, examples:[] } */
const tags = new Map();

const structures = {
  tocTable: makeStruct(),
  imageTable: makeStruct(),
  dataTable: makeStruct(),
  supMarker: makeStruct(), // <sup> elements
  intraPageAnchor: makeStruct(), // <a href="#...">
  blockquote: makeStruct(),
  center: makeStruct(),
  poetryParagraph: makeStruct(), // <p> with >=2 <br>
};

function makeStruct() {
  return { count: 0, books: new Set(), examples: [], extra: {} };
}

function recordStruct(s, book, file, snippet) {
  s.count++;
  s.books.add(book);
  if (s.examples.length < MAX_EXAMPLES_PER_STRUCT) {
    s.examples.push({ file: relForReport(file), snippet: snip(snippet) });
  }
}

function relForReport(absFile) {
  return path.relative(REPO_ROOT, absFile);
}

function snip(s) {
  if (!s) return "";
  const oneLine = s.replace(/\s+/g, " ").trim();
  return oneLine.length > SNIPPET_LEN ? oneLine.slice(0, SNIPPET_LEN) + "…" : oneLine;
}

function getTag(name) {
  let t = tags.get(name);
  if (!t) {
    t = {
      count: 0,
      books: new Set(),
      attrNames: new Map(),
      classVals: new Map(),
      idVals: new Map(),
      examples: [],
    };
    tags.set(name, t);
  }
  return t;
}

function bump(map, key, max) {
  if (map.has(key)) {
    map.set(key, map.get(key) + 1);
  } else if (map.size < max) {
    map.set(key, 1);
  }
}

// anomaly counters
const anomalies = {
  parseErrors: { count: 0, examples: [] },
  emptyBody: { count: 0, examples: [] },
  noBody: { count: 0, examples: [] },
  replacementChar: { count: 0, examples: [] }, // U+FFFD
  windows1256Remnant: { count: 0, examples: [] },
  brokenFootnoteAnchors: { count: 0, examples: [] }, // href="#x" with no matching id/name
};

function recordAnomaly(a, file, note) {
  a.count++;
  if (a.examples.length < 6) a.examples.push({ file: relForReport(file), note: note || "" });
}

let filesScanned = 0;
let filesWithBody = 0;
const allBooks = new Set();

// ---------- per-file analysis ----------
function analyzeFile(absFile, text) {
  const book = bookKeyForFile(absFile);
  allBooks.add(book);

  // encoding oddities
  if (text.includes("�")) recordAnomaly(anomalies.replacementChar, absFile);
  if (/charset\s*=\s*["']?windows-1256/i.test(text) || /encoding\s*=\s*["']?windows-1256/i.test(text)) {
    recordAnomaly(anomalies.windows1256Remnant, absFile);
  }

  // Per-file dedupe so "books a tag appears in" is accurate; count totals globally.
  const tagsThisFile = new Set();

  // Stack of open elements to capture text content of structural blocks.
  // Each frame: { name, attribs, text, html, tabloidStartIdx }
  const stack = [];
  // Collect ids/names present in file and intra-page anchor targets.
  const idsInFile = new Set();
  const anchorTargets = [];

  let sawBody = false;
  let bodyDepth = 0; // >0 means inside <body>
  let bodyTextLen = 0;
  let supInFile = 0;
  let intraAnchorsInFile = 0;
  let blockquoteInFile = 0;
  let centerInFile = 0;
  let hadParseError = false;

  // Buffers for structures currently being captured (need full inner text).
  // We track tables and paragraphs specially.
  const tableFrames = []; // active <table> capture frames
  const pFrames = []; // active <p> frames (to count <br>)

  const firstSnippetForTag = new Map();

  const parser = new Parser(
    {
      onopentag(name, attribs) {
        if (name === "body") {
          sawBody = true;
          bodyDepth++;
        }
        // record id/name for anchor validation
        if (attribs.id) idsInFile.add(attribs.id);
        if (attribs.name) idsInFile.add(attribs.name);

        // tag inventory
        const t = getTag(name);
        t.count++;
        tagsThisFile.add(name);
        for (const [an, av] of Object.entries(attribs)) {
          bump(t.attrNames, an, MAX_ATTR_NAMES);
          if (an === "class" && av) {
            for (const cls of av.split(/\s+/).filter(Boolean)) bump(t.classVals, cls, MAX_CLASS_VALUES);
          }
          if (an === "id" && av) bump(t.idVals, av, MAX_ID_VALUES);
        }

        // structures
        if (name === "table") {
          tableFrames.push({ text: "", hasImagesDir: false, snippetStart: true, buf: "" });
        }
        if (name === "p") {
          pFrames.push({ brCount: 0, text: "" });
        }
        if (name === "br") {
          if (pFrames.length) pFrames[pFrames.length - 1].brCount++;
        }
        if (name === "img") {
          const src = attribs.src || "";
          if (/(^|\/)images\//.test(src) && tableFrames.length) {
            tableFrames[tableFrames.length - 1].hasImagesDir = true;
          }
        }
        if (name === "sup") {
          supInFile++;
        }
        if (name === "a") {
          const href = attribs.href || "";
          if (href.startsWith("#") && href.length > 1) {
            intraAnchorsInFile++;
            anchorTargets.push(href.slice(1));
          }
        }
        if (name === "blockquote") blockquoteInFile++;
        if (name === "center") centerInFile++;

        stack.push({ name, attribs });
      },
      ontext(textChunk) {
        if (bodyDepth > 0) bodyTextLen += textChunk.trim().length;
        if (tableFrames.length) {
          const f = tableFrames[tableFrames.length - 1];
          f.text += textChunk;
        }
        if (pFrames.length) {
          pFrames[pFrames.length - 1].text += textChunk;
        }
        // capture first short snippet per tag (top-of-stack element)
        const top = stack[stack.length - 1];
        if (top && !firstSnippetForTag.has(top.name)) {
          const tx = textChunk.trim();
          if (tx) firstSnippetForTag.set(top.name, tx);
        }
      },
      onclosetag(name) {
        if (name === "p" && pFrames.length) {
          const f = pFrames.pop();
          if (f.brCount >= 2) {
            recordStruct(structures.poetryParagraph, book, absFile, f.text);
          }
        }
        if (name === "table" && tableFrames.length) {
          const f = tableFrames.pop();
          const txt = f.text;
          const isToc = /محتويات|Contents/i.test(txt);
          if (isToc) {
            recordStruct(structures.tocTable, book, absFile, txt);
          } else if (f.hasImagesDir) {
            recordStruct(structures.imageTable, book, absFile, txt);
          } else {
            recordStruct(structures.dataTable, book, absFile, txt);
          }
        }
        if (name === "body" && bodyDepth > 0) bodyDepth--;

        // attach a snippet example to the tag if we have capacity
        const t = tags.get(name);
        if (t && t.examples.length < MAX_EXAMPLES_PER_TAG) {
          const sn = firstSnippetForTag.get(name);
          if (sn) {
            t.examples.push({ file: relForReport(absFile), snippet: snip(sn) });
            firstSnippetForTag.delete(name); // allow another distinct example later
          }
        }
        stack.pop();
      },
      onerror() {
        hadParseError = true;
      },
    },
    { decodeEntities: true, lowerCaseTags: true, lowerCaseAttributeNames: true, recognizeSelfClosing: true }
  );

  parser.write(text);
  parser.end();

  // mark book-spread for tags seen in this file
  for (const name of tagsThisFile) tags.get(name).books.add(book);

  // structure book counters that were counted per-occurrence above already added books.
  // Now per-file aggregates:
  if (supInFile > 0) {
    structures.supMarker.count += supInFile;
    structures.supMarker.books.add(book);
    if (structures.supMarker.examples.length < MAX_EXAMPLES_PER_STRUCT) {
      structures.supMarker.examples.push({ file: relForReport(absFile), snippet: `${supInFile} <sup> in file` });
    }
  }
  if (intraAnchorsInFile > 0) {
    structures.intraPageAnchor.count += intraAnchorsInFile;
    structures.intraPageAnchor.books.add(book);
    if (structures.intraPageAnchor.examples.length < MAX_EXAMPLES_PER_STRUCT) {
      structures.intraPageAnchor.examples.push({
        file: relForReport(absFile),
        snippet: `targets: ${anchorTargets.slice(0, 5).join(", ")}`,
      });
    }
  }
  if (blockquoteInFile > 0) {
    structures.blockquote.count += blockquoteInFile;
    structures.blockquote.books.add(book);
    if (structures.blockquote.examples.length < MAX_EXAMPLES_PER_STRUCT) {
      structures.blockquote.examples.push({ file: relForReport(absFile), snippet: `${blockquoteInFile} blockquote(s)` });
    }
  }
  if (centerInFile > 0) {
    structures.center.count += centerInFile;
    structures.center.books.add(book);
    if (structures.center.examples.length < MAX_EXAMPLES_PER_STRUCT) {
      structures.center.examples.push({ file: relForReport(absFile), snippet: `${centerInFile} <center>` });
    }
  }

  // broken footnote anchors: intra-page targets with no matching id/name
  const broken = anchorTargets.filter((t) => !idsInFile.has(t));
  if (anchorTargets.length > 0 && broken.length === anchorTargets.length) {
    // entire file's intra-page anchors have no in-file target (typical footnote pattern
    // where (1) links point to "#(1)" but the target is plain text, not an id).
    recordAnomaly(
      anomalies.brokenFootnoteAnchors,
      absFile,
      `${broken.length} intra-page anchors, 0 matching ids; e.g. #${broken.slice(0, 3).join(", #")}`
    );
  }

  // anomalies: body
  if (!sawBody) recordAnomaly(anomalies.noBody, absFile);
  else if (bodyTextLen === 0) recordAnomaly(anomalies.emptyBody, absFile);
  else filesWithBody++;

  if (hadParseError) recordAnomaly(anomalies.parseErrors, absFile);
}

// ---------- serialization ----------
function mapToSortedObj(map, cap) {
  const arr = [...map.entries()].sort((a, b) => b[1] - a[1]);
  const sliced = cap ? arr.slice(0, cap) : arr;
  return Object.fromEntries(sliced);
}

function serializeTags() {
  const out = {};
  const sorted = [...tags.entries()].sort((a, b) => b[1].count - a[1].count);
  for (const [name, t] of sorted) {
    out[name] = {
      count: t.count,
      books: t.books.size,
      attrNames: mapToSortedObj(t.attrNames),
      classValues: mapToSortedObj(t.classVals, MAX_CLASS_VALUES),
      idValues: mapToSortedObj(t.idVals, MAX_ID_VALUES),
      examples: t.examples,
    };
  }
  return out;
}

function serializeStructures() {
  const out = {};
  for (const [k, s] of Object.entries(structures)) {
    out[k] = { count: s.count, books: s.books.size, examples: s.examples };
  }
  return out;
}

function serializeAnomalies() {
  const out = {};
  for (const [k, a] of Object.entries(anomalies)) {
    out[k] = { count: a.count, examples: a.examples };
  }
  return out;
}

async function main() {
  const t0 = Date.now();
  await fs.mkdir(OUT_DIR, { recursive: true });

  for await (const file of walkContentFiles(CORPUS_ROOT)) {
    let text;
    try {
      text = await readFileText(file);
    } catch (e) {
      recordAnomaly(anomalies.parseErrors, file, `read error: ${e.message}`);
      continue;
    }
    try {
      analyzeFile(file, text);
    } catch (e) {
      recordAnomaly(anomalies.parseErrors, file, `analyze error: ${e.message}`);
    }
    filesScanned++;
    if (filesScanned % 2000 === 0) {
      process.stderr.write(`  …${filesScanned} files\n`);
    }
  }

  const result = {
    generatedAt: new Date().toISOString(),
    corpusRoot: path.relative(REPO_ROOT, CORPUS_ROOT),
    filesScanned,
    filesWithBody,
    booksSeen: allBooks.size,
    elapsedMs: Date.now() - t0,
    tagCount: tags.size,
    tags: serializeTags(),
    structures: serializeStructures(),
    anomalies: serializeAnomalies(),
  };

  await fs.writeFile(OUT_JSON, JSON.stringify(result, null, 2), "utf8");
  process.stderr.write(
    `Done: ${filesScanned} files, ${tags.size} distinct tags, ${allBooks.size} books in ${(result.elapsedMs / 1000).toFixed(1)}s\n`
  );
  process.stderr.write(`Wrote ${path.relative(REPO_ROOT, OUT_JSON)}\n`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
