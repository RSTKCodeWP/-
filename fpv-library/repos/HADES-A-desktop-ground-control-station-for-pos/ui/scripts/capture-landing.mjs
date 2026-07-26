/* Design-iteration capture for the landing site: serves dist-landing/ and screenshots the
 * page at a series of scroll positions (plus the inner pages) so the scroll choreography can
 * be reviewed frame by frame.
 *
 * Run: node scripts/capture-landing.mjs   (precondition: pnpm build:landing)
 * Output: /tmp/landing-shots/*.png
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";
import { preview } from "vite";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = "/tmp/landing-shots";
fs.mkdirSync(OUT, { recursive: true });
const PORT = 5301;

const server = await preview({ root: ROOT, mode: "landing", preview: { port: PORT } });
const base = `${server.resolvedUrls.local[0]}landing.html`;
console.log(`serving dist-landing at ${base}`);

const browser = await chromium.launch({
  args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--hide-scrollbars"],
});
const context = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
const page = await context.newPage();
page.on("pageerror", (e) => console.error("pageerror:", e.message));
page.on("console", (m) => m.type() === "error" && console.error("console:", m.text()));

await page.goto(base, { waitUntil: "networkidle" });
await page.waitForTimeout(2500); // GLB load + first render

// scroll positions as fractions of full scroll height
const stops = [0, 0.06, 0.12, 0.2, 0.3, 0.42, 0.55, 0.68, 0.8, 0.92, 1];
for (let i = 0; i < stops.length; i++) {
  await page.evaluate((f) => {
    const max = document.documentElement.scrollHeight - innerHeight;
    window.scrollTo({ top: max * f, behavior: "instant" });
  }, stops[i]);
  await page.waitForTimeout(1400); // let reveals + scrub settle
  await page.screenshot({ path: `${OUT}/home-${String(i).padStart(2, "0")}-${stops[i]}.png` });
}

for (const route of ["technology", "team"]) {
  await page.goto(`${base}#/${route}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/${route}-top.png` });
  await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight / 2, behavior: "instant" }));
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/${route}-mid.png` });
  await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "instant" }));
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/${route}-end.png` });
}

console.log("done:", fs.readdirSync(OUT).join(", "));
await browser.close();
await new Promise((r) => server.httpServer.close(() => r()));
