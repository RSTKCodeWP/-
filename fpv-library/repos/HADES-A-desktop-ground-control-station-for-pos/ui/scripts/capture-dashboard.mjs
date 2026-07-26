/* One-off marketing screenshot capture for the HADES web demo dashboard.
 *
 * Serves the built dist-web/ bundle (vite preview, mode "web" — same approach as
 * tests/web-demo.spec.ts), replays the baked mission in plain chromium under
 * swiftshader (MapLibre needs a WebGL context in headless), and captures the
 * Operations dashboard in both themes:
 *   public/landing/dashboard-light.png  (DAY, the default)
 *   public/landing/dashboard-dark.png   (NIGHT, forced via <html data-theme> before load)
 *
 * Run: node scripts/capture-dashboard.mjs   (precondition: pnpm build:web)
 */
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";
import { preview } from "vite";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT_DIR = path.join(ROOT, "public", "landing");
const PORT = 5299; // must not collide with the e2e suite's 5279

const server = await preview({ root: ROOT, mode: "web", preview: { port: PORT } });
const appUrl = server.resolvedUrls.local[0];
console.log(`serving dist-web at ${appUrl}`);

const browser = await chromium.launch({
  // same flags as the e2e suite — without swiftshader MapLibre gets no WebGL → white map
  args: [
    "--use-gl=swiftshader",
    "--enable-unsafe-swiftshader",
    "--ignore-gpu-blocklist",
    "--hide-scrollbars",
  ],
});

async function capture(theme, outfile) {
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1000 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();
  page.on("pageerror", (e) => console.error(`[${theme}] pageerror:`, e));

  if (theme === "night") {
    // The theme store reads <html data-theme> at module import; flipping the attribute
    // before any script runs makes the whole app (map palette included) boot dark, and a
    // fresh page load means the full mission replay repaints the video canvas too.
    await page.addInitScript(() => {
      // init scripts can run before <html> exists — apply as soon as it appears, which is
      // still long before the app's module bundle (where the theme store reads it) executes.
      const apply = () => {
        if (!document.documentElement) return false;
        document.documentElement.setAttribute("data-theme", "night");
        return true;
      };
      if (!apply()) {
        new MutationObserver((_, obs) => {
          if (apply()) obs.disconnect();
        }).observe(document, { childList: true });
      }
    });
  }

  await page.goto(appUrl, { waitUntil: "networkidle" });

  const applied = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
  if (applied !== theme) throw new Error(`theme mismatch: wanted ${theme}, html has ${applied}`);

  // Mission replay plots contacts: the real PINPOINT (track 42) + the CUE_ONLY (track 19).
  await page.getByTestId("row-42").waitFor({ state: "visible", timeout: 30_000 });
  await page.getByTestId("row-19").waitFor({ state: "visible", timeout: 30_000 });
  await page.getByTestId("video-canvas").waitFor({ state: "visible", timeout: 30_000 });

  // Map ready: live handle up, style loaded, and basemap tiles actually painted
  // (queryRenderedFeatures on the fill layers — the basemap.spec.ts technique).
  await page.waitForFunction(() => !!window.__hadesMap, null, { timeout: 20_000 });
  await page.waitForFunction(
    () => {
      const m = window.__hadesMap;
      return m.isStyleLoaded() && m.getSource("basemap") != null;
    },
    null,
    { timeout: 20_000 },
  );
  await page.waitForFunction(
    () => {
      const m = window.__hadesMap;
      const ids = ["earth", "water"].filter((id) => m.getLayer(id));
      if (ids.length === 0) return false;
      return m.queryRenderedFeatures(undefined, { layers: ids }).length > 0;
    },
    null,
    { timeout: 20_000 },
  );

  // Settle: let the ~3s replay finish and map labels/tiles finish compositing.
  await page.waitForTimeout(5_000);

  await page.screenshot({ path: outfile });
  console.log(`captured ${outfile}`);
  await context.close();
}

let failed = false;
try {
  await capture("day", path.join(OUT_DIR, "dashboard-light.png"));
  await capture("night", path.join(OUT_DIR, "dashboard-dark.png"));
} catch (e) {
  failed = true;
  console.error(e);
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(() => resolve()));
}
process.exit(failed ? 1 : 0);
