import "server-only";

import { cache } from "react";
import { promises as fs } from "node:fs";
import path from "node:path";

import type { AuthorInfo } from "./types";

const REPO_ROOT = path.resolve(process.cwd(), "..", "..");
const AUTHORS_ROOT = path.join(REPO_ROOT, "authors");

/** Absolute path to a slug's normalized portrait file (may not exist). */
export function authorPortraitAbsolute(slug: string): string {
  return path.join(AUTHORS_ROOT, slug, "portrait.jpg");
}

export const loadAuthorInfo = cache(async (slug: string): Promise<AuthorInfo | null> => {
  const infoPath = path.join(AUTHORS_ROOT, slug, "info.json");
  try {
    const raw = await fs.readFile(infoPath, "utf8");
    return JSON.parse(raw) as AuthorInfo;
  } catch {
    return null;
  }
});

export const loadAllAuthorInfos = cache(async (): Promise<Map<string, AuthorInfo>> => {
  const map = new Map<string, AuthorInfo>();
  let entries: string[];
  try {
    entries = await fs.readdir(AUTHORS_ROOT);
  } catch {
    return map;
  }
  await Promise.all(
    entries.map(async (slug) => {
      const info = await loadAuthorInfo(slug);
      if (info) map.set(slug, info);
    }),
  );
  return map;
});

/**
 * Resolve the portrait for a slug. Aliases are followed one level to their
 * canonical target. Collections and persons without a usable portrait return
 * a null path. The returned path, when present, is the public `/api/portrait`
 * URL for whichever slug actually owns the image.
 */
export function resolveAuthorPortrait(
  slug: string,
  infos: Map<string, AuthorInfo>,
): { path: string | null; source: string | null } {
  let info = infos.get(slug);
  if (!info) return { path: null, source: null };

  if (info.kind === "alias" && info.aliases_to) {
    const target = infos.get(info.aliases_to);
    if (target) info = target;
  }

  if (info.kind === "collection") return { path: null, source: null };

  if (info.portrait_status === "ok" && info.portrait) {
    return { path: `/api/portrait/${info.slug}`, source: info.portrait_source };
  }
  return { path: null, source: null };
}
