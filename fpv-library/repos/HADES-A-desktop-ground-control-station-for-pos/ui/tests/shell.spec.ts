import path from "node:path";
import { fileURLToPath } from "node:url";

import { test, expect, chromium, type Browser } from "@playwright/test";
import { preview, type PreviewServer } from "vite";

/* UI-overhaul Stage 3 gate — the multi-page console shell (DESIGN-SYSTEM §11). Asserts the
 * persistent mode-switcher rail renders all four modes, switching modes swaps the page region,
 * and — the one cross-page invariant (§11.3, the Lattice lesson) — the global selection spine
 * SURVIVES navigation: a contact selected on OPS is still selected after switching to REVIEW
 * and back. Runs on the real `dist-web` build (a plain chromium tab), the same surface the demo
 * + Electron share. Precondition: `pnpm build:web` produced `dist-web/` (the suite pretest). */

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");

let server: PreviewServer;
let browser: Browser;
let appUrl: string;

test.beforeAll(async () => {
  server = await preview({ root: ROOT, mode: "web", preview: { port: 5283 } });
  appUrl = server.resolvedUrls!.local[0];
  browser = await chromium.launch({
    args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
  });
});

test.afterAll(async () => {
  await browser?.close();
  await new Promise<void>((resolve) => server.httpServer.close(() => resolve()));
});

test("the console rail renders all four modes and switches the page region", async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(appUrl, { waitUntil: "domcontentloaded" });

  // The persistent rail with the four instrument modes.
  const rail = page.getByTestId("console-rail");
  await expect(rail).toBeVisible({ timeout: 20_000 });
  for (const mode of ["ops", "review", "map", "set"]) {
    await expect(page.getByTestId(`nav-${mode}`)).toBeVisible();
  }

  // OPS is the default landing mode; its page is shown.
  await expect(page.getByTestId("page-ops")).toBeVisible();

  // Switch to REVIEW → its page shows, OPS page is gone.
  await page.getByTestId("nav-review").click();
  await expect(page.getByTestId("page-review")).toBeVisible();
  await expect(page.getByTestId("page-ops")).toHaveCount(0);

  // Switch to MAP, then SET.
  await page.getByTestId("nav-map").click();
  await expect(page.getByTestId("page-map")).toBeVisible();
  await page.getByTestId("nav-set").click();
  await expect(page.getByTestId("page-set")).toBeVisible();

  // The status strip + demo banner persist across modes (§11.4).
  await expect(page.getByTestId("status-strip")).toBeVisible();
});

test("the global selection spine survives navigation (§11.3)", async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(appUrl, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("console-rail")).toBeVisible({ timeout: 20_000 });

  // On OPS, select the first contact row. (The demo replays contacts into the rail.)
  const firstRow = page.locator("[data-contact-row]").first();
  await expect(firstRow).toBeVisible({ timeout: 20_000 });
  const selectedTrack = await firstRow.getAttribute("data-track-id");
  await firstRow.click();
  await expect(firstRow).toHaveAttribute("data-selected", "true");

  // Navigate to REVIEW — the SAME contact must still be the selection there.
  await page.getByTestId("nav-review").click();
  await expect(page.getByTestId("page-review")).toBeVisible();
  await expect(
    page.locator(`[data-track-id="${selectedTrack}"][data-selected="true"]`).first(),
  ).toBeVisible();

  // Back to OPS — still selected.
  await page.getByTestId("nav-ops").click();
  await expect(page.getByTestId("page-ops")).toBeVisible();
  await expect(
    page.locator(`[data-track-id="${selectedTrack}"][data-selected="true"]`).first(),
  ).toBeVisible();
});
