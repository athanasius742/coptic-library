"use client";

import { useEffect, useState } from "react";

import { CopticMoon } from "./coptic-moon";
import { CopticSun } from "./coptic-sun";

type Theme = "light" | "dark";

/**
 * Sun/moon theme toggle. SSR renders no `data-theme`, which resolves to the
 * default dark styles; the inline bootstrap script in layout.tsx applies the
 * stored theme before paint. We initialize state from the actual DOM attribute
 * in an effect (and only render the icon once mounted) to avoid a hydration
 * mismatch / flash of the wrong glyph.
 */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const current = document.documentElement.getAttribute("data-theme");
    setTheme(current === "light" ? "light" : "dark");
    setMounted(true);
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("theme", next);
    } catch {
      // localStorage may be unavailable (private mode); theme still applies.
    }
    setTheme(next);
  }

  // In dark mode we show the moon (click -> go light); in light, the sun.
  const goingToLight = theme === "dark";
  const label = goingToLight ? "Switch to light theme" : "Switch to dark theme";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className="cursor-pointer rounded-full p-2 text-gold-200 transition hover:text-gold-50"
    >
      {/* Render a stable placeholder until mounted to keep SSR/CSR markup
          aligned; swap to the correct glyph after we read the DOM attribute. */}
      {mounted && !goingToLight ? (
        <CopticSun size={20} />
      ) : (
        <CopticMoon size={20} />
      )}
    </button>
  );
}
