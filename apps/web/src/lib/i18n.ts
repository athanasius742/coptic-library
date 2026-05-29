export type Locale = "ar" | "en";

export const LOCALES: Locale[] = ["ar", "en"];
export const DEFAULT_LOCALE: Locale = "ar";

export function isLocale(value: string | undefined): value is Locale {
  return value === "ar" || value === "en";
}

type Dict = Record<Locale, string>;

const STRINGS = {
  // Site / brand
  "site.title": {
    ar: "مكتبة الكتب القبطية الأرثوذكسية",
    en: "Coptic Orthodox Library",
  },
  "site.title.template": {
    ar: "%s · مكتبة الكتب القبطية الأرثوذكسية",
    en: "%s · Coptic Orthodox Library",
  },
  "site.description": {
    ar: "مكتبة رقمية لكتب الآباء والمعلمين في الكنيسة القبطية الأرثوذكسية.",
    en: "A digital library of the works of the Fathers and Teachers of the Coptic Orthodox Church.",
  },
  "site.brand.line1": {
    ar: "مكتبة الكتب القبطية",
    en: "Coptic Orthodox Library",
  },
  "site.brand.line2": {
    ar: "Coptic Orthodox Library",
    en: "A Library of the Holy Fathers",
  },

  // Nav
  "nav.home": { ar: "الرئيسية", en: "Home" },
  "nav.authors": { ar: "المؤلفون", en: "Authors" },
  "nav.books": { ar: "الكتب", en: "Books" },

  // Language switch
  "lang.arabic": { ar: "العربية", en: "العربية" },
  "lang.english": { ar: "English", en: "English" },
  "lang.switch": { ar: "اللغة", en: "Language" },

  // Footer
  "footer.glory": { ar: "المجد لله", en: "Glory to God" },
  "footer.about": { ar: "حول المكتبة", en: "About" },
  "footer.github": { ar: "المصدر على GitHub", en: "Source on GitHub" },
  "footer.epub": { ar: "حول صيغة EPUB", en: "About the EPUB format" },

  // EPUB info button / popover
  "epub.info.aria": { ar: "حول صيغة EPUB", en: "About the EPUB format" },
  "epub.info.body": {
    ar: "صيغة EPUB تعطيك الكتاب كنصٍّ حقيقي (وليس صورة)، فيمكنك تكبير الخط، وتحديد أي جزء ونسخه ولصقه والبحث فيه وتظليله — قراءة مريحة على أي جهاز.",
    en: "EPUB gives you the book as real text (not a picture), so you can enlarge the font and easily select, copy, paste, search, and highlight anything — comfortable reading on any device.",
  },
  "epub.info.readMore": { ar: "اعرف المزيد ←", en: "Read more →" },

  // Home / hero
  "home.hero.eyebrow": {
    ar: "مكتبة الآباء القديسين",
    en: "· A Library of the Holy Fathers ·",
  },
  "home.hero.lead": {
    ar: "مجموعة مختارة من كتب آباء الكنيسة والمعلمين الأرثوذكس، بين يديك في حلّة جديدة.",
    en: "A curated collection of works by the Fathers and Teachers of the Orthodox Church, presented anew.",
  },

  // About page
  "about.title": { ar: "حول المكتبة", en: "About" },
  "about.placeholder": {
    ar: "قريبًا.",
    en: "Coming soon.",
  },
  "home.cta.browseBooks": { ar: "تصفّح الكتب", en: "Browse Books" },
  "home.cta.browseAuthors": { ar: "تصفّح المؤلفين", en: "Browse Authors" },
  "home.stat.books": { ar: "كتاب", en: "Books" },
  "home.stat.authors": { ar: "مؤلف", en: "Authors" },
  "home.stat.arabic.label": { ar: "باللغة العربية", en: "In Arabic" },
  "home.stat.arabic.value": { ar: "100%", en: "100%" },
  "home.section.authors.eyebrow": { ar: "الآباء", en: "The Fathers" },
  "home.section.authors.title": {
    ar: "مؤلفون من الآباء والمعلمين",
    en: "Fathers and Teachers",
  },
  "home.section.authors.cta": { ar: "كل المؤلفين", en: "All Authors" },
  "home.section.books.eyebrow": { ar: "مختارات", en: "Selected Works" },
  "home.section.books.title": {
    ar: "مختارات من الكتب",
    en: "Selected Works",
  },
  "home.section.books.cta": { ar: "كل الكتب", en: "All Books" },

  // Author cards
  "author.bookCount.short": { ar: "كتب", en: "books" },

  // Authors index
  "authors.eyebrow": { ar: "الآباء", en: "The Fathers" },
  "authors.title": { ar: "المؤلفون", en: "Authors" },
  "authors.subtitle.suffix": { ar: "مؤلفًا", en: "authors" },

  // Author detail
  "author.eyebrow": { ar: "من آباء الكنيسة", en: "· A Father of the Church ·" },
  "author.subtitle.suffix": { ar: "كتابًا في المكتبة", en: "books in the library" },

  // Books index
  "books.eyebrow": { ar: "مختارات", en: "Selected Works" },
  "books.title": { ar: "الكتب", en: "Books" },
  "books.search.placeholder": {
    ar: "ابحث في عناوين الكتب والمؤلفين…",
    en: "Search book titles and authors…",
  },
  "books.count.singular.suffix": { ar: "كتابًا", en: "books" },
  "books.count.of": { ar: "من", en: "of" },
  "books.empty": { ar: "لا توجد نتائج مطابقة.", en: "No matching results." },
  "books.notAvailableEn": {
    ar: "غير متوفر بالإنجليزية",
    en: "Not available in English",
  },

  // Book detail
  "book.fromSource.prefix": { ar: "من", en: "· From" },
  "book.fromSource.suffix": { ar: "", en: "·" },
  "book.downloadEpub": { ar: "تنزيل EPUB", en: "Download EPUB" },
  "book.sourceLink": { ar: "المصدر الأصلي", en: "Original Source" },
  "book.field.chapters": { ar: "عدد الفصول", en: "Chapters" },
  "book.field.language": { ar: "اللغة", en: "Language" },
  "book.field.language.ar": { ar: "العربية", en: "Arabic" },
  "book.field.language.en": { ar: "الإنجليزية", en: "English" },
  "book.field.series": { ar: "السلسلة", en: "Series" },
  "book.field.source": { ar: "المصدر", en: "Source" },
  "book.toc.eyebrow": { ar: "فهرس المحتويات", en: "· Table of Contents ·" },
  "book.toc.title": { ar: "فهرس الكتاب", en: "Table of Contents" },
  "book.toc.startReading": {
    ar: "ابدأ القراءة من الفصل الأول ←",
    en: "Start reading from chapter one →",
  },
  "book.arabicOnlyBanner.title": {
    ar: "هذا الكتاب متاح بالعربية فقط",
    en: "This book is only available in Arabic",
  },
  "book.arabicOnlyBanner.body": {
    ar: "لم يتم بعد توفير ترجمة إنجليزية لهذا الكتاب. المحتوى أدناه باللغة العربية.",
    en: "No English translation is available for this book yet. The content below is in Arabic.",
  },

  // Chapter
  "chapter.eyebrow.prefix": { ar: "الفصل", en: "· Chapter" },
  "chapter.eyebrow.of": { ar: "من", en: "of" },
  "chapter.eyebrow.suffix": { ar: "", en: "·" },
  "chapter.from": { ar: "من", en: "From" },
  "chapter.prev": { ar: "← السابق", en: "← Previous" },
  "chapter.next": { ar: "التالي →", en: "Next →" },
  "chapter.toc": { ar: "فهرس الكتاب", en: "Table of Contents" },

  // Misc
  "common.notFound.book": { ar: "كتاب", en: "Book" },
  "common.notFound.author": { ar: "مؤلف", en: "Author" },
  "common.notFound.chapter": { ar: "فصل", en: "Chapter" },
} satisfies Record<string, Dict>;

export type StringKey = keyof typeof STRINGS;

export function t(locale: Locale, key: StringKey): string {
  return STRINGS[key][locale];
}

export function dirFor(locale: Locale): "rtl" | "ltr" {
  return locale === "ar" ? "rtl" : "ltr";
}

export function langFor(locale: Locale): string {
  return locale === "ar" ? "ar" : "en";
}

export function fontClassFor(locale: Locale): string {
  // Arabic UI uses the Amiri/arabic family; English UI prefers the body serif.
  return locale === "ar" ? "font-arabic" : "font-body";
}
