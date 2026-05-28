import type { Metadata } from "next";
import { headers } from "next/headers";
import { Cinzel, Source_Serif_4 } from "next/font/google";
import localFont from "next/font/local";

import { dirFor, isLocale, langFor, type Locale } from "@/lib/i18n";

import "./globals.css";

// Thmanyah Sans — self-hosted from /public/fonts. The official typeface of
// the Thmanyah publishing house (ثمانية), a distinctive contemporary Naskh.
const thmanyah = localFont({
  variable: "--font-amiri", // keep the existing CSS variable name to avoid touching every consumer
  src: [
    { path: "../../public/fonts/thmanyah-sans-400.woff2", weight: "400", style: "normal" },
    { path: "../../public/fonts/thmanyah-sans-700.woff2", weight: "700", style: "normal" },
  ],
  display: "swap",
});

const cinzel = Cinzel({
  variable: "--font-cinzel",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const sourceSerif = Source_Serif_4({
  variable: "--font-cormorant",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
};

async function resolveLocale(): Promise<Locale> {
  // The middleware injects `x-locale` for every request so we can pick the
  // right lang/dir to render on <html>. Falls back to "ar" (which is also the
  // redirect target for `/`).
  try {
    const h = await headers();
    const fromHeader = h.get("x-locale");
    if (isLocale(fromHeader ?? undefined)) return fromHeader as Locale;
    const path = h.get("x-pathname") ?? "/";
    const seg = path.split("/").filter(Boolean)[0];
    if (isLocale(seg)) return seg;
  } catch {
    // ignore
  }
  return "ar";
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const locale = await resolveLocale();
  return (
    <html
      lang={langFor(locale)}
      dir={dirFor(locale)}
      className={`${thmanyah.variable} ${cinzel.variable} ${sourceSerif.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
