import path from "node:path";
import { fileURLToPath } from "node:url";

import { test, expect, chromium } from "@playwright/test";
import { createServer, type ViteDevServer } from "vite";

/* Glass-to-glass latency measurement (impl-plan Task 5.11 / M3). Runs the app (mock-driven,
 * deterministic), lets it paint a few seconds of frames, then reads back the in-app latency
 * report (socket-receive → painted-with-overlay) and asserts the ≤120 ms in-app budget.
 *
 * Honest provenance (recorded in docs/plans/p5-latency-budget.md): this measures the IN-APP
 * path on the CI/dev machine under software GL — it proves the in-app stages are well within
 * budget and exercises the instrument; the binding field ≤120 ms gate is a manual on-device
 * run on the M4-class target. Drone-link latency is excluded (outside the app). */

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BUDGET_MS = 120;

let viteServer: ViteDevServer;
let appUrl: string;

test.beforeAll(async () => {
  viteServer = await createServer({ root: path.resolve(__dirname, ".."), server: { port: 5278 } });
  await viteServer.listen();
  appUrl = viteServer.resolvedUrls!.local[0];
  // NOTE: the browser is launched per-attempt INSIDE the test (a fresh GPU process), not here —
  // see the rationale in the test body.
});

test.afterAll(async () => {
  await viteServer?.close();
});

test("M3: in-app glass-to-glass latency is within the ≤120ms budget", async () => {
  // Use a DEDICATED fresh browser, not the shared suite one: this spec runs late, after the
  // map/demo specs have hammered the single swiftshader GPU process; a crashed GPU process there
  // would starve frame capture here (it can't paint 20 frames). A fresh browser gets a fresh GPU
  // process, isolating this performance probe from accumulated WebGL pressure. We also retry the
  // whole capture once if the GPU dies mid-run.
  const launch = () =>
    chromium.launch({ args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });

  const capture = async () => {
    const b = await launch();
    try {
      const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
      await page.addInitScript(() => {
        (window as unknown as { __imp: (p: string) => Promise<unknown> }).__imp = (p: string) =>
          import(/* @vite-ignore */ p);
      });
      await page.goto(appUrl, { waitUntil: "networkidle" });
      await page.waitForFunction(
        async () => {
          const m = await (window.__imp!("/src/perf/latency.ts") as Promise<typeof import("../src/perf/latency")>);
          return m.latencyMeter.count >= 20;
        },
        { timeout: 30_000 },
      );
      return await page.evaluate(async () => {
        const m = await (window.__imp!("/src/perf/latency.ts") as Promise<typeof import("../src/perf/latency")>);
        const r = m.latencyMeter.report();
        return { count: r.count, p50: r.p50Ms, p95: r.p95Ms, max: r.maxMs, mean: r.meanMs };
      });
    } finally {
      await b.close();
    }
  };

  let report;
  try {
    report = await capture();
  } catch {
    report = await capture(); // one in-test retry on a GPU-process crash
  }

  // eslint-disable-next-line no-console
  console.log(
    `[M3 latency] n=${report.count} p50=${report.p50.toFixed(1)}ms ` +
      `p95=${report.p95.toFixed(1)}ms max=${report.max.toFixed(1)}ms mean=${report.mean.toFixed(1)}ms`,
  );

  expect(report.count).toBeGreaterThanOrEqual(20);
  expect(report.p95).toBeLessThanOrEqual(BUDGET_MS); // the in-app glass-to-glass gate
});

declare global {
  interface Window {
    __imp?: (p: string) => Promise<unknown>;
  }
}
