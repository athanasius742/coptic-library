/**
 * Reading-progress store — one record per book in localStorage, holding the
 * reader's current position (chapter + scroll %) plus a denormalized snapshot
 * of the display fields (title/author/cover) so the "Currently Reading" shelf
 * renders entirely client-side with no catalog payload or API round-trip.
 *
 * This is the localStorage half of the deliberate "mock user" seam (see
 * mock-user.ts). When real auth + a DB land, the server will instead JOIN book
 * metadata onto a stored position and these functions become API calls — the
 * UI consuming them shouldn't need to change. Every read/write is SSR-safe
 * (guards `window`) and swallows errors (private mode / quota), matching the
 * theme / reading-font-scale contract.
 */

export type ReadingProgress = {
  authorSlug: string;
  bookSlug: string;
  // current position
  chapterSlug: string;
  chapterIndex: number; // 0-based
  totalChapters: number;
  scrollProgress: number; // 0..100 through the CURRENT chapter
  updatedAt: number; // Date.now() — for "most recent" sort
  // denormalized display snapshot (so the shelf needs no server data)
  bookTitle: string;
  bookTitleEn?: string;
  author: string;
  authorEn?: string;
  coverPath: string; // /api/cover/{author}/{book}
  language?: string; // for the Arabic-only / font handling
  chapterTitle: string;
};

// Versioned key so a future schema change can migrate / ignore old data cleanly.
const STORAGE_KEY = "reading-progress-v1";

type ProgressMap = Record<string, ReadingProgress>;

function progressKey(authorSlug: string, bookSlug: string): string {
  return `${authorSlug}/${bookSlug}`;
}

function readMap(): ProgressMap {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") return parsed as ProgressMap;
  } catch {
    // malformed / unavailable storage — treat as empty, never throw.
  }
  return {};
}

function writeMap(map: ProgressMap): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    // quota / private mode — silently drop, same contract as theme/font-scale.
  }
}

/** All progress records, most-recently-updated first. */
export function getAllProgress(): ReadingProgress[] {
  return Object.values(readMap()).sort((a, b) => b.updatedAt - a.updatedAt);
}

export function getProgress(
  authorSlug: string,
  bookSlug: string,
): ReadingProgress | null {
  return readMap()[progressKey(authorSlug, bookSlug)] ?? null;
}

/**
 * Merge a record into the keyed map (one entry per book) and stamp updatedAt.
 * Caller passes everything except updatedAt.
 */
export function upsertProgress(
  rec: Omit<ReadingProgress, "updatedAt">,
): void {
  const map = readMap();
  map[progressKey(rec.authorSlug, rec.bookSlug)] = {
    ...rec,
    updatedAt: Date.now(),
  };
  writeMap(map);
}

export function removeProgress(authorSlug: string, bookSlug: string): void {
  const map = readMap();
  delete map[progressKey(authorSlug, bookSlug)];
  writeMap(map);
}

export function clearAllProgress(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

/**
 * Overall progress through the whole book, 0..100, combining the completed
 * chapters with the scroll position in the current one. Guards a zero/empty
 * chapter count so the bar never divides by zero.
 */
export function overallPercent(rec: ReadingProgress): number {
  const total = Math.max(rec.totalChapters, 1);
  const fraction = (rec.chapterIndex + rec.scrollProgress / 100) / total;
  return Math.min(100, Math.max(0, Math.round(fraction * 100)));
}

export { STORAGE_KEY as READING_PROGRESS_KEY };
