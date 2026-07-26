import path from "node:path";
import { fileURLToPath } from "node:url";

import { test, expect, chromium, type Browser } from "@playwright/test";
import { preview, type PreviewServer } from "vite";

/* UI-overhaul Stage 1.1 gate — the offline basemap must render REAL tile content, not just our
 * overlays. The original "empty map" was a flat dark fill because no PMTiles basemap existed
 * (see docs/plans/ui-overhaul-investigation.md). We now bundle a Protomaps v4 extract of the
 * Biloxi / MS-Gulf-Coast AO under ui/public/ and load it over the offline `pmtiles://` protocol.
 *
 * Asserting "the map isn't empty" via WebGL pixel readback is unreliable (preserveDrawingBuffer
 * is false → drawImage off the GL canvas reads black). Instead we query the live MapLibre map
 * (exposed on window.__hadesMap for tests) with queryRenderedFeatures on the basemap layers and
 * assert tile features actually painted. This fails on the OLD code (flat fill, no basemap
 * source) and passes on the new (real terrain renders).
 *
 * Precondition: `pnpm build:web` produced `dist-web/` (the suite's pretest builds it). */

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");

let server: PreviewServer;
let browser: Browser;
let appUrl: string;

test.beforeAll(async () => {
  server = await preview({ root: ROOT, mode: "web", preview: { port: 5282 } });
  appUrl = server.resolvedUrls!.local[0];
  // swiftshader so MapLibre gets a real (software) WebGL context in headless CI.
  browser = await chromium.launch({
    args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
  });
});

test.afterAll(async () => {
  await browser?.close();
  await new Promise<void>((resolve) => server.httpServer.close(() => resolve()));
});

test("the offline PMTiles basemap renders real terrain tiles (map is no longer empty)", async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // The basemap file must actually be served (a 404 here is the exact original failure mode).
  const basemap404: string[] = [];
  page.on("response", (r) => {
    if (r.url().includes("biloxi-coastal.pmtiles") && r.status() >= 400) {
      basemap404.push(`${r.status()} ${r.url()}`);
    }
  });

  await page.goto(appUrl, { waitUntil: "domcontentloaded" });

  // Map mounts (not the WebGL-unavailable fallback).
  await expect(page.getByTestId("map-view")).toBeVisible({ timeout: 20_000 });

  // Wait for the live map handle, then for the basemap source's tiles to load.
  await page.waitForFunction(() => !!window.__hadesMap, null, { timeout: 20_000 });
  await page.waitForFunction(
    () => {
      const m = window.__hadesMap!;
      return m.isStyleLoaded() && m.getSource("basemap") != null;
    },
    null,
    { timeout: 20_000 },
  );

  // Poll queryRenderedFeatures on the basemap fill layers (earth = land, water) until tiles
  // have painted. This is the real "non-empty tile content, not just our overlays" assertion.
  const renderedBasemapFeatures = await page
    .waitForFunction(
      () => {
        const m = window.__hadesMap!;
        const ids = ["earth", "water"].filter((id) => m.getLayer(id));
        if (ids.length === 0) return false;
        const n = m.queryRenderedFeatures(undefined as never, { layers: ids }).length;
        return n > 0 ? n : false;
      },
      null,
      { timeout: 20_000 },
    )
    .then((h) => h.jsonValue());

  expect(basemap404, "basemap PMTiles must be served, not 404").toEqual([]);
  expect(renderedBasemapFeatures, "basemap tile features must render").toBeGreaterThan(0);
});
