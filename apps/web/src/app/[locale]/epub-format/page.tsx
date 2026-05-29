import { notFound } from "next/navigation";

import { CrossDivider } from "@/components/ornament";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { dirFor, isLocale, t, type Locale } from "@/lib/i18n";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: rawLocale } = await params;
  if (!isLocale(rawLocale)) return {};
  const locale: Locale = rawLocale;
  return { title: t(locale, "site.title.template").replace("%s", PAGE[locale].title) };
}

export default async function EpubFormatPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: rawLocale } = await params;
  if (!isLocale(rawLocale)) notFound();
  const locale: Locale = rawLocale;
  const isAr = locale === "ar";
  const dir = dirFor(locale);
  const c = PAGE[locale];

  return (
    <>
      <SiteHeader locale={locale} />
      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-14" dir={dir}>
        {/* Hero */}
        <header className="text-center">
          <p
            className={`text-gold-600 ${
              isAr
                ? "font-ruqaa text-base"
                : "font-display text-[10px] uppercase tracking-[0.45em]"
            }`}
          >
            {c.eyebrow}
          </p>
          <h1
            className={`mt-3 text-4xl font-bold text-gold-100 sm:text-5xl ${
              isAr ? "font-arabic" : "font-display tracking-wide"
            }`}
          >
            {c.title}
          </h1>
          <p
            className={`mx-auto mt-5 max-w-2xl text-base text-bone/80 ${
              isAr ? "font-arabic" : "font-body"
            }`}
            dir={dir}
          >
            {c.lead}
          </p>
        </header>

        <CrossDivider />

        {/* What EPUB is */}
        <Section title={c.whatTitle} isAr={isAr} dir={dir} paras={c.whatParas} />

        {/* EPUB vs PDF */}
        <Section title={c.pdfTitle} isAr={isAr} dir={dir} paras={c.pdfParas} />
        <ComparisonTable
          locale={locale}
          dir={dir}
          caption={c.tableCaption}
          head={c.tableHead}
          rows={c.tableRows}
        />

        {/* EPUB vs a webpage */}
        <Section title={c.webTitle} isAr={isAr} dir={dir} paras={c.webParas} />

        {/* Why it's better for reading */}
        <Section title={c.whyTitle} isAr={isAr} dir={dir} paras={c.whyIntro}>
          <ul className="mt-3 space-y-2 ps-5" dir={dir}>
            {c.whyList.map((item) => (
              <li key={item} className="list-disc text-bone/90 marker:text-gold-600">
                {item}
              </li>
            ))}
          </ul>
        </Section>

        {/* Where you can read it */}
        <Section title={c.whereTitle} isAr={isAr} dir={dir} paras={c.whereParas} />

        {/* How to open an EPUB — per platform */}
        <section className="mt-12" dir={dir}>
          <SectionHeading title={c.howTitle} isAr={isAr} />
          <div className="prose-coptic !max-w-none" dir={dir}>
            {c.howIntro.map((p, i) => (
              <p key={i} className="!text-base">
                {p}
              </p>
            ))}
          </div>
          <div className="mt-6 space-y-6">
            {c.platforms.map((plat) => (
              <div
                key={plat.name}
                className="border border-gold-800/60 bg-ink/40 p-5"
              >
                <h3
                  className={`text-lg font-bold text-gold-100 ${
                    isAr ? "font-arabic" : "font-display tracking-wide"
                  }`}
                >
                  {plat.name}
                </h3>
                <p
                  className={`mt-1 text-sm text-bone/80 ${
                    isAr ? "font-arabic" : "font-body"
                  }`}
                  dir={dir}
                >
                  {plat.note}
                </p>
                <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
                  {plat.links.map((lnk) => (
                    <li key={lnk.href}>
                      <a
                        href={lnk.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-bold text-gold-100 underline decoration-gold/50 underline-offset-4 transition hover:text-gold-50 hover:decoration-gold"
                      >
                        {lnk.label} ↗
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>

        <CrossDivider />

        <p
          className={`text-center text-base text-bone/80 ${
            isAr ? "font-arabic" : "font-body"
          }`}
          dir={dir}
        >
          {c.closing}
        </p>
      </main>
      <SiteFooter locale={locale} />
    </>
  );
}

/* ---------- Small presentational helpers ---------- */

function SectionHeading({ title, isAr }: { title: string; isAr: boolean }) {
  return (
    <h2
      className={`mb-3 text-2xl font-bold text-gold-50 ${
        isAr ? "font-arabic" : "font-display tracking-wide"
      }`}
    >
      {title}
    </h2>
  );
}

function Section({
  title,
  paras,
  isAr,
  dir,
  children,
}: {
  title: string;
  paras: string[];
  isAr: boolean;
  dir: "rtl" | "ltr";
  children?: React.ReactNode;
}) {
  return (
    <section className="mt-12" dir={dir}>
      <SectionHeading title={title} isAr={isAr} />
      <div className="prose-coptic !max-w-none" dir={dir}>
        {paras.map((p, i) => (
          <p key={i} className="!text-base">
            {p}
          </p>
        ))}
      </div>
      {children}
    </section>
  );
}

function ComparisonTable({
  locale,
  dir,
  caption,
  head,
  rows,
}: {
  locale: Locale;
  dir: "rtl" | "ltr";
  caption: string;
  head: [string, string, string];
  rows: [string, string, string][];
}) {
  const isAr = locale === "ar";
  const fontClass = isAr ? "font-arabic" : "font-body";
  return (
    <div className="not-prose mt-6 overflow-x-auto" dir={dir}>
      <table className={`content-table w-full border-collapse text-sm ${fontClass}`}>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h} className="bg-ink/50">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="text-bone">
          {rows.map((row) => (
            <tr key={row[0]}>
              <th scope="row" className="bg-ink/30 text-start">
                {row[0]}
              </th>
              <td>{row[1]}</td>
              <td>{row[2]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------- Per-locale article content ---------- */

type PlatformLink = { label: string; href: string };
type Platform = { name: string; note: string; links: PlatformLink[] };

type PageContent = {
  eyebrow: string;
  title: string;
  lead: string;
  whatTitle: string;
  whatParas: string[];
  pdfTitle: string;
  pdfParas: string[];
  tableCaption: string;
  tableHead: [string, string, string];
  tableRows: [string, string, string][];
  webTitle: string;
  webParas: string[];
  whyTitle: string;
  whyIntro: string[];
  whyList: string[];
  whereTitle: string;
  whereParas: string[];
  howTitle: string;
  howIntro: string[];
  platforms: Platform[];
  closing: string;
};

// Verified official download links (see research). Shared across locales.
const LINKS = {
  playBooks:
    "https://play.google.com/store/apps/details?id=com.google.android.apps.books",
  moonReader:
    "https://play.google.com/store/apps/details?id=com.flyersoft.moonreader",
  librera: "https://play.google.com/store/apps/details?id=com.foobnix.pdf.reader",
  readEra: "https://play.google.com/store/apps/details?id=org.readera",
  appleBooks: "https://apps.apple.com/app/apple-books/id364709193",
  calibre: "https://calibre-ebook.com/download",
  thorium: "https://thorium.edrlab.org/en/",
  foliate: "https://flathub.org/apps/com.github.johnfactotum.Foliate",
  sendToKindle: "https://www.amazon.com/sendtokindle",
  kobo: "https://help.kobo.com/hc/en-us/articles/360020121953-Install-Kobo-Desktop-on-your-PC-or-Mac",
};

const PAGE: Record<Locale, PageContent> = {
  en: {
    eyebrow: "· A Gentle Guide ·",
    title: "What's the EPUB format?",
    lead: "When you download a book here, you get an EPUB file. This short guide explains, in plain language, what that is and how to read it comfortably on any phone, tablet, or computer.",

    whatTitle: "What is an EPUB?",
    whatParas: [
      "An EPUB (you can say it “EE-pub”) is the standard format for e-books — the digital equivalent of a printed book. One EPUB file holds the whole book: every page, chapter, and image, all in a single file you keep on your device.",
      "The most important thing to know is that the text inside an EPUB is real, living text — not a photograph of a page. That means the words can flow and rearrange themselves to fit your screen, and you can make them bigger or smaller whenever you like. This is called a “reflowable” format, and it is what makes reading on a phone so comfortable.",
    ],

    pdfTitle: "EPUB vs. PDF",
    pdfParas: [
      "Many people have only ever read e-books as PDFs, so it helps to compare the two. A PDF is a fixed-layout format: it preserves the exact look of a printed page, like a photo of that page. On a large screen this is fine, but on a phone the whole page is shrunk to fit, leaving the text tiny — so you end up pinching and dragging around just to read one paragraph.",
      "An EPUB is different. Because the text reflows, it always fills your screen at whatever size you choose. (To be fair, a PDF can also contain selectable text — it is not always just an image — but it stays locked to its fixed page layout, while an EPUB adapts to you.)",
    ],
    tableCaption: "A comparison of the EPUB and PDF formats.",
    tableHead: ["", "EPUB", "PDF"],
    tableRows: [
      ["Layout", "Reflows to fit any screen", "Fixed, like a photo of a page"],
      ["Change font size", "Yes, freely", "No — you can only zoom in/out"],
      ["Comfortable on a phone", "Yes", "Often requires pinching & scrolling"],
      ["Dark / night mode", "Yes, in most readers", "Rarely"],
      ["Select, copy & search text", "Yes", "Sometimes (if it has real text)"],
      ["Remembers your place", "Yes", "Usually not"],
    ],

    webTitle: "EPUB vs. a web page",
    webParas: [
      "You could, of course, just read these books on the website. So why download an EPUB? Because an EPUB is a single, self-contained file that you download and truly own. The whole book lives in that one file.",
      "That means it works completely offline — on a long flight, in church, or anywhere with no signal. It is designed for long, restful reading rather than quick browsing, and a good reading app will remember exactly where you stopped and open right back to that spot next time.",
    ],

    whyTitle: "Why EPUB is better for reading",
    whyIntro: [
      "All of this adds up to a calmer, kinder reading experience — especially for longer, prayerful books:",
    ],
    whyList: [
      "Adjustable font size — a real blessing for older eyes; make the text as large as you need.",
      "Night and sepia modes — gentle on the eyes for reading in the evening or in low light.",
      "Highlights and notes — mark a passage that moves you and write your own reflections beside it.",
      "Copy and paste — quote a line into a message, a sermon, or your notes in seconds.",
      "Full-text search — find any word, name, or verse instantly across the whole book.",
      "Syncing — many apps keep your place and notes in step across your phone, tablet, and computer.",
    ],

    whereTitle: "Where can you read an EPUB?",
    whereParas: [
      "Almost everywhere. You can read EPUBs on dedicated e-readers like Amazon Kindle and Kobo, on Android and iPhone, on iPad and other tablets, and on Windows, macOS, and Linux computers.",
      "Good news for Kindle owners: Amazon now accepts EPUB files. Using the free “Send to Kindle” service (by email, the app, or the website), you send the EPUB to your account and Amazon automatically converts it to read on your Kindle — you no longer need the old MOBI format. Kobo e-readers, for their part, read EPUB files directly with no conversion at all.",
    ],

    howTitle: "How to open an EPUB",
    howIntro: [
      "You only need a free reading app, installed once. Pick your device below and tap an official link to install it, then open the EPUB file you downloaded. All of these links go to the official source for each app.",
    ],
    platforms: [
      {
        name: "Android phone or tablet",
        note: "Any of these free apps will open EPUB files. Google Play Books is the simplest if you already use Google.",
        links: [
          { label: "Google Play Books", href: LINKS.playBooks },
          { label: "Moon+ Reader", href: LINKS.moonReader },
          { label: "Librera", href: LINKS.librera },
          { label: "ReadEra", href: LINKS.readEra },
        ],
      },
      {
        name: "iPhone or iPad",
        note: "Apple Books is already built into your device — just open the EPUB and choose “Copy to Books”. (If it was ever removed, you can reinstall it free below.)",
        links: [{ label: "Apple Books", href: LINKS.appleBooks }],
      },
      {
        name: "Windows computer",
        note: "Windows has no built-in EPUB reader (Microsoft Edge dropped that feature), so install one of these free apps.",
        links: [
          { label: "Thorium Reader", href: LINKS.thorium },
          { label: "Calibre", href: LINKS.calibre },
        ],
      },
      {
        name: "Mac (macOS)",
        note: "Apple Books comes built in — just double-click the EPUB. Calibre or Thorium are good alternatives.",
        links: [
          { label: "Apple Books", href: LINKS.appleBooks },
          { label: "Calibre", href: LINKS.calibre },
          { label: "Thorium Reader", href: LINKS.thorium },
        ],
      },
      {
        name: "Linux computer",
        note: "Several free, open-source readers handle EPUB beautifully.",
        links: [
          { label: "Foliate", href: LINKS.foliate },
          { label: "Calibre", href: LINKS.calibre },
          { label: "Thorium Reader", href: LINKS.thorium },
        ],
      },
      {
        name: "Amazon Kindle (device or app)",
        note: "Use the free “Send to Kindle” service to send the EPUB to your Kindle; Amazon converts it automatically.",
        links: [{ label: "Send to Kindle", href: LINKS.sendToKindle }],
      },
      {
        name: "Kobo e-reader",
        note: "Kobo reads EPUB files directly — just copy the file onto the device, or use the free Kobo app on your computer.",
        links: [{ label: "Kobo desktop app", href: LINKS.kobo }],
      },
    ],

    closing:
      "That's all there is to it. Download the EPUB, open it in any reader above, and enjoy the book at whatever size and in whatever light feels most restful to you. Glory to God.",
  },

  ar: {
    eyebrow: "· دليل مبسّط ·",
    title: "ما هي صيغة EPUB؟",
    lead: "عند تنزيل أي كتاب من هنا تحصل على ملف بصيغة EPUB. يشرح لك هذا الدليل القصير، بكلمات بسيطة، ما هي هذه الصيغة وكيف تقرأ بها براحة على أي هاتف أو جهاز لوحي أو حاسوب.",

    whatTitle: "ما هي صيغة EPUB؟",
    whatParas: [
      "صيغة EPUB (تُنطق «إي-پَب») هي الصيغة القياسية للكتب الإلكترونية، أي ما يقابل الكتاب المطبوع في العالم الرقمي. ملف EPUB واحد يحوي الكتاب كاملًا: كل الصفحات والفصول والصور في ملف واحد تحتفظ به على جهازك.",
      "وأهم ما ينبغي أن تعرفه هو أن النص داخل ملف EPUB نصٌّ حقيقي حيّ، وليس صورةً فوتوغرافية للصفحة. هذا يعني أن الكلمات تتدفّق وتُعيد ترتيب نفسها لتناسب شاشتك، ويمكنك تكبيرها أو تصغيرها متى شئت. تُسمّى هذه الصيغة «المتدفّقة» (reflowable)، وهي ما يجعل القراءة على الهاتف مريحةً للغاية.",
    ],

    pdfTitle: "EPUB مقابل PDF",
    pdfParas: [
      "اعتاد كثيرون قراءة الكتب الإلكترونية بصيغة PDF فقط، لذا تفيد المقارنة بين الصيغتين. صيغة PDF ثابتة التخطيط: تحفظ شكل الصفحة المطبوعة كما هو تمامًا، كأنها صورة لتلك الصفحة. هذا جيد على الشاشات الكبيرة، أما على الهاتف فتُصغَّر الصفحة كلها لتلائم الشاشة، فيصبح النص دقيقًا جدًّا، وتضطر إلى التكبير والتحريك يمينًا ويسارًا لتقرأ فقرةً واحدة.",
      "أما EPUB فمختلفة. فلأن النص يتدفّق، يملأ شاشتك دائمًا بالحجم الذي تختاره أنت. (وللإنصاف: قد يحوي ملف PDF أيضًا نصًّا قابلًا للتحديد، فهو ليس دائمًا مجرّد صورة، لكنه يبقى مقيَّدًا بتخطيط صفحته الثابت، بينما تتكيّف صيغة EPUB معك أنت.)",
    ],
    tableCaption: "مقارنة بين صيغتَي EPUB و PDF.",
    tableHead: ["", "EPUB", "PDF"],
    tableRows: [
      ["التخطيط", "يتدفّق ليلائم أي شاشة", "ثابت، كصورةٍ للصفحة"],
      ["تغيير حجم الخط", "نعم، بحرّية", "لا، يمكنك التكبير والتصغير فقط"],
      ["الراحة على الهاتف", "نعم", "غالبًا يحتاج تكبيرًا وتمريرًا"],
      ["الوضع الليلي", "نعم، في معظم البرامج", "نادرًا"],
      ["تحديد النص ونسخه والبحث فيه", "نعم", "أحيانًا (إن كان نصًّا حقيقيًّا)"],
      ["يتذكّر موضع توقّفك", "نعم", "غالبًا لا"],
    ],

    webTitle: "EPUB مقابل صفحة الويب",
    webParas: [
      "يمكنك بالطبع أن تقرأ هذه الكتب على الموقع مباشرةً، فلماذا تنزّل ملف EPUB إذًا؟ لأن ملف EPUB ملفٌّ واحد مكتفٍ بذاته، تنزّله فيصير ملكًا لك حقًّا. الكتاب كله موجود في هذا الملف الواحد.",
      "وهذا يعني أنه يعمل بلا إنترنت تمامًا: في رحلة طويلة، أو في الكنيسة، أو في أي مكان بلا تغطية. وهو مصمَّمٌ للقراءة الطويلة المتأنّية لا للتصفّح السريع، كما أن أي برنامج قراءة جيّد سيتذكّر بالضبط أين توقّفت ويفتح لك من حيث انتهيت في المرة التالية.",
    ],

    whyTitle: "لماذا تكون EPUB أفضل للقراءة؟",
    whyIntro: [
      "كل ما سبق يجتمع ليمنحك تجربة قراءة أهدأ وألطف، خاصةً مع الكتب الطويلة والروحية:",
    ],
    whyList: [
      "حجم خط قابل للتعديل — نعمة حقيقية لمن كبرت أعينهم؛ كبِّر النص بالقدر الذي تحتاجه.",
      "الوضع الليلي والسيبيا — لطيفٌ على العين للقراءة مساءً أو في الإضاءة الخافتة.",
      "التظليل والملاحظات — ضع علامةً على مقطعٍ لمس قلبك، واكتب تأمّلاتك بجواره.",
      "النسخ واللصق — انقل سطرًا إلى رسالة أو عظة أو ملاحظاتك في ثوانٍ.",
      "البحث في كامل النص — اعثر على أي كلمة أو اسم أو آية فورًا في الكتاب كله.",
      "المزامنة — كثير من البرامج تُبقي موضعك وملاحظاتك متوافقة بين هاتفك وجهازك اللوحي وحاسوبك.",
    ],

    whereTitle: "أين يمكنك قراءة ملف EPUB؟",
    whereParas: [
      "في كل مكان تقريبًا. يمكنك قراءة ملفات EPUB على القارئات المخصّصة مثل Amazon Kindle و Kobo، وعلى هواتف Android و iPhone، وعلى iPad وغيره من الأجهزة اللوحية، وعلى حواسيب Windows و macOS و Linux.",
      "وخبرٌ سار لأصحاب Kindle: صار Amazon الآن يقبل ملفات EPUB. فعبر خدمة «Send to Kindle» المجانية (بالبريد الإلكتروني أو التطبيق أو الموقع) ترسل ملف EPUB إلى حسابك، ويحوّله Amazon تلقائيًّا لتقرأه على جهاز Kindle، ولم تعد بحاجةٍ إلى صيغة MOBI القديمة. أما قارئات Kobo فتقرأ ملفات EPUB مباشرةً دون أي تحويل.",
    ],

    howTitle: "كيف تفتح ملف EPUB؟",
    howIntro: [
      "كل ما تحتاجه هو برنامج قراءة مجاني، تثبّته مرّةً واحدة. اختر جهازك في الأسفل واضغط على رابطٍ رسمي لتثبيت البرنامج، ثم افتح ملف EPUB الذي نزّلته. كل هذه الروابط تؤدّي إلى المصدر الرسمي لكل برنامج.",
    ],
    platforms: [
      {
        name: "هاتف أو جهاز Android لوحي",
        note: "أيٌّ من هذه البرامج المجانية يفتح ملفات EPUB. وبرنامج Google Play Books هو الأبسط إن كنت تستخدم Google أصلًا.",
        links: [
          { label: "Google Play Books", href: LINKS.playBooks },
          { label: "Moon+ Reader", href: LINKS.moonReader },
          { label: "Librera", href: LINKS.librera },
          { label: "ReadEra", href: LINKS.readEra },
        ],
      },
      {
        name: "iPhone أو iPad",
        note: "برنامج Apple Books مثبَّتٌ مسبقًا على جهازك — افتح ملف EPUB واختر «نسخ إلى الكتب». (وإن كان قد حُذف يومًا، يمكنك إعادة تثبيته مجانًا من الرابط أدناه.)",
        links: [{ label: "Apple Books", href: LINKS.appleBooks }],
      },
      {
        name: "حاسوب Windows",
        note: "لا يحوي Windows قارئًا مدمجًا لصيغة EPUB (فقد أزال متصفّح Microsoft Edge هذه الميزة)، لذا ثبّت أحد هذين البرنامجين المجانيين.",
        links: [
          { label: "Thorium Reader", href: LINKS.thorium },
          { label: "Calibre", href: LINKS.calibre },
        ],
      },
      {
        name: "حاسوب Mac (نظام macOS)",
        note: "برنامج Apple Books مدمجٌ في الجهاز — يكفي أن تنقر نقرًا مزدوجًا على ملف EPUB. وبرنامجا Calibre و Thorium بديلان ممتازان.",
        links: [
          { label: "Apple Books", href: LINKS.appleBooks },
          { label: "Calibre", href: LINKS.calibre },
          { label: "Thorium Reader", href: LINKS.thorium },
        ],
      },
      {
        name: "حاسوب Linux",
        note: "هناك عدّة برامج قراءة مجانية ومفتوحة المصدر تتعامل مع صيغة EPUB ببراعة.",
        links: [
          { label: "Foliate", href: LINKS.foliate },
          { label: "Calibre", href: LINKS.calibre },
          { label: "Thorium Reader", href: LINKS.thorium },
        ],
      },
      {
        name: "Amazon Kindle (الجهاز أو التطبيق)",
        note: "استخدم خدمة «Send to Kindle» المجانية لإرسال ملف EPUB إلى جهازك؛ ويحوّله Amazon تلقائيًّا.",
        links: [{ label: "Send to Kindle", href: LINKS.sendToKindle }],
      },
      {
        name: "قارئ Kobo",
        note: "يقرأ Kobo ملفات EPUB مباشرةً — يكفي أن تنسخ الملف إلى الجهاز، أو تستخدم تطبيق Kobo المجاني على حاسوبك.",
        links: [{ label: "تطبيق Kobo للحاسوب", href: LINKS.kobo }],
      },
    ],

    closing:
      "هذا كل ما في الأمر. نزّل ملف EPUB، وافتحه بأي برنامج من البرامج أعلاه، واستمتع بالكتاب بالحجم وبالإضاءة اللذين يريحانك أكثر. المجد لله.",
  },
};
