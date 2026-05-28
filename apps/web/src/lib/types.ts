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
};
