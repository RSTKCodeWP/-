import path from "node:path";
import { fileURLToPath } from "node:url";

import { test, expect, chromium, type Browser } from "@playwright/test";
import { preview, type PreviewServer } from "vite";

/* The front-facing DEMONSTRATION site v2 (all-white 3D hero, hash-routed pages). Asserts the
 * marketing pages render their sections, the live-demo CTA points at the demo build, the
 * before/after wipe responds, and the FAQ accordion expands (Technology page). Runs on the real
 * `dist-landing` build; the suite pretest builds it (`vite build --mode landing`). */

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");

let server: PreviewServer;
let browser: Browser;
let appUrl: string;

test.beforeAll(async () => {
  server = await preview({
    root: ROOT,
    build: { outDir: "dist-landing" },
    preview: { port: 5284 },
  });
  appUrl = server.resolvedUrls!.local[0];
  browser = await chromium.launch({
    args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
  });
});

test.afterAll(async () => {
  await browser?.close();
  await new Promise<void>((resolve) => server.httpServer.close(() => resolve()));
});

test("home renders the hero, partner logos, real metrics, and no demo links", async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`${appUrl}landing.html`, { waitUntil: "networkidle" });

  // the static floating-drone hero: the HADES wordmark + the drone render
  await expect(page.locator(".hero-word")).toHaveText("HADES");
  await expect(page.locator(".hero-drone")).toBeVisible();
  // the mission statement sits below the tall hero (scrubbed reveals start visibility:hidden,
  // so they are absent from the a11y tree; assert presence by class/text, not role)
  await expect(page.locator(".statement-kick")).toHaveText(/the mission/i);
  await expect(page.locator(".statement-text")).toContainText(/turns a live drone feed into located survivors/i);

  // the demo console is not linked from the site, anywhere
  await expect(page.locator('a[href*="demo"], a[href*="index.html"]')).toHaveCount(0);

  // recognition strip: all four partner logos resolve. They are lazy-loaded below the tall
  // hero, so scroll them into view and wait for decode before asserting naturalWidth.
  await page.evaluate(() => document.querySelector(".logo-strip")?.scrollIntoView());
  await page.waitForTimeout(800);
  for (const alt of [
    "Duke Pratt School of Engineering",
    "MIT Solve",
    "Day of AI",
    "North Carolina Science and Engineering Fair",
    "Samsung Solve for Tomorrow",
  ]) {
    const img = page.getByAltText(alt).first();
    await expect(img).toBeAttached();
    await expect
      .poll(async () => img.evaluate((el: HTMLImageElement) => el.naturalWidth), { timeout: 8000 })
      .toBeGreaterThan(0);
  }

  // the real, honest metric figures (count-up targets). Jump to the bottom so the metrics
  // pass through their reveal + count-up triggers, then assert the final values landed in DOM.
  await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "instant" }));
  await page.waitForTimeout(2000);
  await expect(page.locator(".metric-num").filter({ hasText: "0.85" })).toHaveCount(1, { timeout: 10_000 });
  await expect(page.locator(".metric-num").filter({ hasText: "22.4" })).toHaveCount(1, { timeout: 10_000 });
});

test("the before/after wipe reveals detections on drag", async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`${appUrl}landing.html`, { waitUntil: "networkidle" });

  const wrap = page.locator(".ba-wrap");
  await wrap.scrollIntoViewIfNeeded();
  await expect(wrap.getByAltText(/same frame with hades detections/i)).toBeAttached();

  // reveals settle asynchronously — wait for layout to go quiet, then re-scroll and measure
  // fresh so the drag coordinates aren't stale
  await page.waitForTimeout(1200);
  await wrap.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);

  const handle = page.locator(".ba-handle");
  const box = (await wrap.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.85, box.y + box.height * 0.5, { steps: 4 });
  await page.mouse.up();
  const after = await handle.evaluate((el) => el.style.left);
  expect(parseFloat(after)).toBeGreaterThan(70);
});

test("the technology page answers the connection question (FAQ accordion)", async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`${appUrl}landing.html#/technology`, { waitUntil: "networkidle" });

  await expect(page.getByRole("heading", { name: /search party/i })).toBeVisible();

  // the FAQ sits below scrubbed reveals; drive the page to the bottom so those sections
  // reveal (become visible + enter the a11y tree) before interacting
  await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "instant" }));
  await page.waitForTimeout(1200);

  // the first question ("Does it work without a connection?") ships open by default
  const first = page.locator(".faq-q", { hasText: /does it work without a connection/i });
  await first.scrollIntoViewIfNeeded();
  await expect(first).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByText(/run entirely on the laptop with the network off/i)).toBeVisible();

  // a closed one expands on click
  const q = page.locator(".faq-q", { hasText: /how accurate is the detection/i });
  await expect(q).toHaveAttribute("aria-expanded", "false");
  await q.click();
  await expect(q).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByText(/0\.85 recall on the HERIDAL/i)).toBeVisible();
});

test("the team page shows the team, the build, and recognition", async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`${appUrl}landing.html#/team`, { waitUntil: "networkidle" });

  await expect(page.getByRole("heading", { name: /students who/i })).toBeVisible();
  // the face-in-circle team grid: one avatar per member
  await expect(page.locator(".team-member")).toHaveCount(4);
  await expect(page.getByAltText(/assembled hades airframe/i)).toBeAttached();
  await expect(page.getByText(/samsung solve for tomorrow/i).first()).toBeAttached();
});
