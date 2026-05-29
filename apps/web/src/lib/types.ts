export type CatalogEntry = {
  book_id: string;
  index_url: string;
  family: string;
  author_slug: string;
  book_slug: string;
  title_guess: string | null;
  author_guess: string | null;
  cover_url: string | null;
  dest: string;
  section: string;
  chapter_links_guess: number;
  status: string;
};

export type BookMeta = {
  slug: string;
  title: string;
  title_en?: string;
  author: string;
  author_en?: string;
  author_slug: string;
  source: string;
  source_url: string;
  topics?: string[];
  series?: string;
  series_en?: string;
  description?: string;
  description_en?: string;
  keywords?: string[];
  epub?: string;
  cover?: string;
  language?: string;
};

export type Chapter = {
  order: number;
  slug: string;
  file: string;
  title: string;
  url: string;
};

export type Book = BookMeta & {
  authorSlug: string;
  bookSlug: string;
  chapterCount: number;
  coverPath: string;
};

export type Author = {
  slug: string;
  name: string;
  bookCount: number;
  portraitPath: string | null;
};

export type AuthorInfo = {
  slug: string;
  kind: "person" | "collection" | "alias";
  name_ar: string;
  name_en: string;
  bio_ar: string | null;
  bio_en: string | null;
  birth_year: number | null;
  death_year: number | null;
  portrait: string | null;
  portrait_source: string | null;
  portrait_status: "ok" | "not_found" | "license_unclear" | "n/a" | "missing" | null;
  wikipedia_ar: string | null;
  wikipedia_en: string | null;
  aliases_to: string | null;
  note?: string;
  // Additive fields written by the publishing pipeline (tools/resolve_author.py,
  // PLAN §6.5). Optional and ignored by the current reader.
  match_key?: string[];
  aliases_ar?: string[];
  aliases_en?: string[];
  bio_source?: string | null;
  portrait_license?: string | null;
  authority?: {
    wikidata?: string | null;
    viaf?: string | null;
    loc?: string | null;
  };
  resolution?: {
    confidence?: number;
    method?: string;
    matched_slug?: string | null;
    source_surface?: string;
    reviewed?: boolean;
    needs_review?: boolean;
    ts?: string;
  };
};
