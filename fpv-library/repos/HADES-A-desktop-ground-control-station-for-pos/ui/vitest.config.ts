import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/* Vitest = unit/logic + component tests (store, mock-ws, selection spine, formatters,
 * React components via jsdom). Co-located test files end in .test.ts / .test.tsx under src.
 * Playwright (Electron E2E specs under tests/) is a SEPARATE runner — excluded here so the
 * two never collide (Playwright's `test` global is incompatible with Vitest's). */

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    exclude: ["node_modules", "dist", "dist-electron", "tests"],
  },
});
