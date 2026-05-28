import type { MetadataRoute } from "next";

import { loadAllBooks, loadAuthors, loadChapters } from "@/lib/catalog";
import { LOCALES } from "@/lib/i18n";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [books, authors] = await Promise.all([loadAllBooks(), loadAuthors()]);
  const root: MetadataRoute.Sitemap = [];
  for (const locale of LOCALES) {
    root.push(
      { url: `${BASE}/${locale}`, changeFrequency: "weekly", priority: 1 },
      { url: `${BASE}/${locale}/authors`, changeFrequency: "monthly", priority: 0.8 },
      { url: `${BASE}/${locale}/books`, changeFrequency: "monthly", priority: 0.8 },
    );
    for (const a of authors) {
      root.push({
        url: `${BASE}/${locale}/authors/${a.slug}`,
        changeFrequency: "monthly",
        priority: 0.6,
      });
    }
    for (const b of books) {
      root.push({
        url: `${BASE}/${locale}/books/${b.authorSlug}/${b.bookSlug}`,
        changeFrequency: "monthly",
        priority: 0.7,
      });
      const chapters = await loadChapters(b.authorSlug, b.bookSlug);
      for (const c of chapters) {
        root.push({
          url: `${BASE}/${locale}/books/${b.authorSlug}/${b.bookSlug}/${c.slug}`,
          changeFrequency: "yearly",
          priority: 0.5,
        });
      }
    }
  }
  return root;
}
