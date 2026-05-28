#!/usr/bin/env node
// Smoke-crawl the chapter renderer across a spread of books.
//
// Builds chapter URLs programmatically from each book's manifest.json + meta.json
// (locale follows the BOOK's language, not the UI), then asserts each page returns
// HTTP 200 with a non-empty <article> body. Logs non-200s, empty bodies, and any
// pages whose body still leaks a raw `images/` <img>.
//
// Usage: node apps/web/scripts/smoke-crawl.mjs [baseUrl] [count]
//   baseUrl defaults to http://localhost:3000
//   count   max number of URLs to crawl (default 50)

import { promises as fs } from "node:fs";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "../../..");
const BOOKS = path.join(ROOT, "books", "st-takla.org");
const BASE = process.argv[2] || "http://localhost:3000";
const MAX = Number(process.argv[3] || 50);

// Fixture URLs we always want covered (locale = book language).
const FIXTURES = [
  "/ar/books/anba-raphael/i-willingly-ate/sinned-in-adam",
  "/ar/books/adel-zekri/augustine-consentius-120/text",
  "/en/books/ecf/004/0040047",
  "/ar/books/anba-raphael/i-willingly-ate/foreword",
];

async function readJson(p) {
  return JSON.parse(await fs.readFile(p, "utf8"));
}

async function listBooks() {
  const out = [];
  const authors = await fs.readdir(BOOKS, { withFileTypes: true });
  for (const a of authors) {
    if (!a.isDirectory()) continue;
    const adir = path.join(BOOKS, a.name);
    const books = await fs.readdir(adir, { withFileTypes: true });
    for (const b of books) {
      if (!b.isDirectory()) continue;
      out.push({ author: a.name, book: b.name, dir: path.join(adir, b.name) });
    }
  }
  return out;
}

// Spread picks: every Nth book, first non-index chapter of each.
async function buildUrlList() {
  const books = await listBooks();
  const urls = new Set(FIXTURES);
  // Deterministic spread across the whole catalog.
  const step = Math.max(1, Math.floor(books.length / (MAX * 1.5)));
  for (let i = 0; i < books.length && urls.size < MAX; i += step) {
    const { author, book, dir } = books[i];
    let meta, manifest;
    try {
      meta = await readJson(path.join(dir, "meta.json"));
      manifest = await readJson(path.join(dir, "manifest.json"));
    } catch {
      continue;
    }
    const locale = meta.language === "en" ? "en" : "ar";
    const chapters = manifest.filter(
      (c) => !(c.order === 0 && c.slug === "index"),
    );
    if (chapters.length === 0) continue;
    // pick a middle-ish chapter so we exercise content, not just title pages
    const ch = chapters[Math.floor(chapters.length / 2)];
    urls.add(`/${locale}/books/${author}/${book}/${ch.slug}`);
  }
  return [...urls].slice(0, MAX);
}

function articleBody(html) {
  const m = html.match(/<article[^>]*>([\s\S]*?)<\/article>/i);
  if (!m) return null;
  // strip tags + whitespace to gauge visible text length
  return m[1].replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

async function main() {
  const urls = await buildUrlList();
  console.log(`Crawling ${urls.length} URLs against ${BASE}\n`);
  const failures = [];
  const empties = [];
  const imageLeaks = [];
  let ok = 0;

  for (const u of urls) {
    let res, html;
    try {
      res = await fetch(BASE + u);
      html = await res.text();
    } catch (e) {
      failures.push({ u, status: "FETCH_ERR", msg: String(e) });
      continue;
    }
    const body = articleBody(html);
    const bodyLen = body ? body.length : 0;
    if (res.status !== 200) {
      failures.push({ u, status: res.status });
    } else if (bodyLen < 40) {
      empties.push({ u, bodyLen });
    } else {
      ok++;
    }
    if (/<img[^>]+src=["'][^"']*images\//i.test(html)) {
      imageLeaks.push(u);
    }
    const flag = res.status !== 200 ? "FAIL" : bodyLen < 40 ? "EMPTY" : "ok";
    console.log(`${String(res.status).padEnd(4)} ${String(bodyLen).padStart(6)}  ${flag.padEnd(5)} ${u}`);
  }

  console.log(`\n=== SUMMARY ===`);
  console.log(`total:     ${urls.length}`);
  console.log(`200+body:  ${ok}`);
  console.log(`failures:  ${failures.length}`);
  console.log(`empties:   ${empties.length}`);
  console.log(`imageLeaks:${imageLeaks.length}`);
  if (failures.length) console.log("FAILURES:", JSON.stringify(failures, null, 2));
  if (empties.length) console.log("EMPTIES:", JSON.stringify(empties, null, 2));
  if (imageLeaks.length) console.log("IMAGE LEAKS:", JSON.stringify(imageLeaks, null, 2));

  process.exit(failures.length || empties.length || imageLeaks.length ? 1 : 0);
}

main();
