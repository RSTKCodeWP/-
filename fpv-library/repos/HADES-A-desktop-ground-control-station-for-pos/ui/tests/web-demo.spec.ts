import path from "node:path";
import { fileURLToPath } from "node:url";

import { test, expect, chromium, type Browser } from "@playwright/test";
import { preview, type PreviewServer } from "vite";

/* Phase 6 Task 6.3 — the static demo site gate. Serves the REAL `dist-web/` build over HTTP
 * (never file://, which CORS-blocks fetch of sibling assets) in a PLAIN chromium tab (NOT
 * Electron — the demo's new runtime), and asserts the baked mission replays end-to-end through
 * the shared UI: the honest demo banner shows, a REAL located survivor (a PINPOINT — only a
 * genuinely localized contact reaches that class) appears in the list, the honest CUE_ONLY
 * no-fix contact also appears, and the video panel paints. DOM-only assertions, so the test runs
 * against the production bundle (no dev-server `/src/...` module paths).
 *
 * Precondition: `pnpm build:web` produced `dist-web/`; the suite's `pretest:e2e` builds, and we
 * `vite preview --mode web` that output here. */

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");

let server: PreviewServer;
let browser: Browser;
let appUrl: string;

test.beforeAll(async () => {
  // serve the built static bundle exactly as a host would (relative base, real fetch path).
  server = await preview({ root: ROOT, mode: "web", preview: { port: 5279 } });
  appUrl = server.resolvedUrls!.local[0];
  browser = await chromium.launch({
    args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
  });
});

test.afterAll(async () => {
  await browser?.close();
  await new Promise<void>((resolve) => server.httpServer.close(() => resolve()));
});

test("static web demo replays the baked mission through the full UI", async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(appUrl, { waitUntil: "networkidle" });

  // the honest demo-mode banner is present (provenance loaded from the baked mission.json) and
  // states exactly which numbers are real — the credibility anchor of the whole demo.
  const banner = page.getByTestId("demo-banner");
  await expect(banner).toBeVisible();
  await expect(banner).toContainText(/DEMO MODE/i);
  await expect(banner).toContainText(/real pipeline/i);
  await expect(banner).toContainText(/no live feed/i);

  // a REAL located survivor reaches PINPOINT (track 42 refines to PINPOINT @ fid 40) — only a
  // genuinely localized contact can; its row appearing proves the demo map has a real pin, not
  // an empty charcoal canvas. The CUE_ONLY no-fix contact (track 19) also appears (honesty).
  await expect(page.getByTestId("row-42")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("row-42")).toContainText("PINPOINT");
  await expect(page.getByTestId("row-19")).toContainText("CUE_ONLY");

  // the video panel paints (binary frame channel replays) and the canvas is present
  await expect(page.getByTestId("video-canvas")).toBeVisible();

  // no uncaught page errors during replay (e.g. the MapLibre glyphs-throw class)
  expect(errors, errors.join("\n")).toEqual([]);

  await page.close();
});
