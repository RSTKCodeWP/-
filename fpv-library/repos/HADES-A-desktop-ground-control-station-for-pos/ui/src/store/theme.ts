import { create } from "zustand";

/* The theme store (UI overhaul §2.5). Both ECDIS-style modes ship: DAY (light, the default,
 * for sunlit field tents) and NIGHT (the original dark palette, for dark ops rooms). The
 * default is set on `<html data-theme="day">` in index.html so the right palette paints on the
 * first frame (no flash); this store drives the runtime toggle, writing the attribute that the
 * `[data-theme="day"]` token override keys off (night = no override = the `:root` defaults). */

export type Theme = "day" | "night";

function readInitial(): Theme {
  if (typeof document === "undefined") return "day";
  return document.documentElement.getAttribute("data-theme") === "night" ? "night" : "day";
}

function apply(theme: Theme) {
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-theme", theme);
  }
}

interface ThemeState {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: readInitial(),
  setTheme: (theme) => {
    apply(theme);
    set({ theme });
  },
  toggle: () => get().setTheme(get().theme === "day" ? "night" : "day"),
}));
