import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Theme = "dark" | "light";

const KEY = "sage-theme";

export function initialTheme(): Theme {
  const saved = (typeof localStorage !== "undefined" && localStorage.getItem(KEY)) as Theme | null;
  if (saved === "dark" || saved === "light") return saved;
  return "dark"; // command-center default
}

/** Apply the theme attribute as early as possible to avoid a flash. */
export function applyThemeAttr(theme: Theme) {
  document.documentElement.dataset.theme = theme;
}

interface ThemeCtx {
  theme: Theme;
  toggle: () => void;
  setTheme: (t: Theme) => void;
}

const Ctx = createContext<ThemeCtx>({ theme: "dark", toggle: () => {}, setTheme: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    applyThemeAttr(theme);
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  const toggle = () => setTheme((t) => (t === "dark" ? "light" : "dark"));
  return <Ctx.Provider value={{ theme, toggle, setTheme }}>{children}</Ctx.Provider>;
}

export const useTheme = () => useContext(Ctx);

/** Free CARTO basemap matched to the theme (no map token required). */
export function basemapFor(theme: Theme): string {
  return theme === "light"
    ? "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
    : "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
}
