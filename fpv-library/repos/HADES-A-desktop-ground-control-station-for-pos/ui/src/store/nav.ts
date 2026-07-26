import { create } from "zustand";

/* The console-mode store (UI overhaul §11) — which of the four instrument modes is active.
 * State, NOT a URL router: these are app modes, not deep-linkable pages, and a history router
 * would break the packaged `file://` deploy (the same `base:"./"` constraint that governs
 * assets, DESIGN-SYSTEM §9.2). Like the selection spine, the mode is a tiny global store, so
 * switching modes never touches — and is never touched by — the selection/contact/telemetry
 * stores. That independence is exactly why the selection spine survives navigation (§11.3). */

export type ConsoleMode = "ops" | "review" | "map" | "set";

export const CONSOLE_MODES: ConsoleMode[] = ["ops", "review", "map", "set"];

interface NavState {
  mode: ConsoleMode;
  setMode: (m: ConsoleMode) => void;
  reset: () => void;
}

export const useNavStore = create<NavState>((set) => ({
  mode: "ops", // OPS (the live instrument) is the default landing mode
  setMode: (mode) => set({ mode }),
  reset: () => set({ mode: "ops" }),
}));
