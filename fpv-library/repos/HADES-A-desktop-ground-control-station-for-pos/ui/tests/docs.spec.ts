import path from "node:path";
import { fileURLToPath } from "node:url";

import { test, expect, chromium, type Browser } from "@playwright/test";
import { preview, type PreviewServer } from "vite";

/* Phase 7 Task 7.6 - the in-app docs page gate. The Docs panel renders the SAME content family
 * as the README (logo, the four metric families with their real figures, the tool list), styled
 * to the design system. Because the Electron app, web app, and demo site all share this React
 * UI, the Docs panel appears in all three from one source - so testing it on the real `dist-web/`
 * build (a plain chromium tab) is sufficient to prove it ships everywhere.
 *
 * Precondition: `pnpm build:web` produced `dist-web/` (the suite's pretest builds it). */

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");

let server: PreviewServer;
let browser: Browser;
let appUrl: string;

test.beforeAll(async () => {
  server = await preview({ root: ROOT, mode: "web", preview: { port: 5281 } });
  appUrl = server.resolvedUrls!.local[0];
  browser = await chromium.launch({
    args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
  });
});

test.afterAll(async () => {
  await browser?.close();
  await new Promise<void>((resolve) => server.httpServer.close(() => resolve()));
});

test("the in-app docs panel renders the logo, a metric figure, and the tool list", async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const failedImages: string[] = [];
  // Catch a broken figure/logo URL (wrong relative base) as a real failure, not a silent gap.
  page.on("response", (r) => {
    if (r.url().includes("/docs/") && r.status() >= 400) failedImages.push(`${r.status()} ${r.url()}`);
  });
  await page.goto(appUrl, { waitUntil: "domcontentloaded" });

  // Open the Docs panel from the always-on toggle in the status strip.
  const toggle = page.getByTestId("docs-toggle");
  await expect(toggle).toBeVisible({ timeout: 20_000 });
  await toggle.click();

  const docs = page.getByTestId("docs-panel");
  await expect(docs).toBeVisible();

  // 1. The logo renders (and actually loads, not a broken-image box).
  const logo = docs.getByTestId("docs-logo");
  await expect(logo).toBeVisible();
  await expect
    .poll(() => logo.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0))
    .toBe(true);

  // 2. At least one real metric figure renders and loads.
  const figure = docs.getByTestId("docs-figure").first();
  await expect(figure).toBeVisible();
  await expect
    .poll(() => figure.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0))
    .toBe(true);

  // 3. The Built-with tool list is present with real, versioned tools.
  const tools = docs.getByTestId("docs-tools");
  await expect(tools).toBeVisible();
  await expect(tools).toContainText(/YOLO11/i);
  await expect(tools).toContainText(/Core ML/i);
  await expect(docs).toContainText("960"); // the shipped detector resolution (in the tables)

  // 4. The honesty disclosures the README carries are present in-app too.
  await expect(docs).toContainText(/sim/i);
  await expect(docs).toContainText(/dev.?floor/i);

  // No broken doc asset requests.
  expect(failedImages, failedImages.join("\n")).toEqual([]);

  // The toggle returns to the mission view (it is a panel, not a dead end).
  await page.getByTestId("docs-close").click();
  await expect(page.getByTestId("status-strip")).toBeVisible();

  await page.close();
});
