import path from "node:path";
import { pathToFileURL } from "node:url";

import { test, expect, _electron as electron } from "@playwright/test";
import type { ElectronApplication, Page } from "@playwright/test";

let app: ElectronApplication;
let page: Page;

// The window Electron main loads via loadFile(); used to recover if firstWindow() catches a
// transient chrome-error page mid-navigation under suite load.
const APP_FILE_URL = pathToFileURL(path.resolve(process.cwd(), "dist", "index.html")).href;

test.beforeAll(async () => {
  // Launch the built Electron app (pretest runs `vite build`, producing
  // dist-electron/main.js and dist/index.html).
  app = await electron.launch({ args: ["."] });
  page = await app.firstWindow();

  // When this (the heaviest-launch spec) runs LAST in the suite — after the service-spawning E2E
  // tests have churned the machine — `firstWindow()` can capture the window MID-NAVIGATION, on a
  // transient `chrome-error://chromewebdata/` page, before Electron's `loadFile(dist/index.html)`
  // settles. If we caught the error frame, navigate the page to the real app document so the test
  // asserts on the app, not the transient error page. (A reload would just reload the error page.)
  for (let i = 0; i < 10; i++) {
    if (await page.locator("#app-root").count()) break;
    await page.goto(APP_FILE_URL, { waitUntil: "domcontentloaded" }).catch(() => {});
    await page.waitForTimeout(400);
  }
});

test.afterAll(async () => {
  await app?.close();
});

test("electron window opens and renders the app root", async () => {
  // The window exists.
  expect(page).toBeTruthy();

  // Wait for the document to load before asserting on its content — an Electron cold launch can
  // be slow to paint when this (the heaviest-launch spec) runs LAST, after the service-spawning
  // E2E tests have loaded the machine. Without this gate the default 5s element timeout can lapse
  // before `index.html` even parses (the #app-root-count-0 flake). The host page is static HTML.
  await page.waitForLoadState("domcontentloaded");

  // The renderer mounted into #app-root.
  const root = page.locator("#app-root");
  await expect(root).toHaveCount(1, { timeout: 15_000 });

  // React mounted the coordinator shell (the always-on status strip is the top landmark; the
  // P0-scaffold placeholder heading this once checked was replaced by the real UI in P5).
  await expect(page.getByTestId("status-strip")).toBeVisible({ timeout: 15_000 });
});
