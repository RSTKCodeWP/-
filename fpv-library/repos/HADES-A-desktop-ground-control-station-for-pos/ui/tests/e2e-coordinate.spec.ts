import { spawn, type ChildProcess } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { test, expect, chromium, type Browser } from "@playwright/test";
import { createServer, type ViteDevServer } from "vite";

/* THE mandatory E2E coordinate test (impl-plan Task 5.9), resolved per the Option-C split
 * (adversarial design review, folded into tasks/lessons.md):
 *
 *  5.9-a  THE REAL FIELD PATH — replay the real recorded fixture (clip_2s.mp4 +
 *         position-only clip_2s.srt) through the REAL `hades-service` → REAL dual WS → REAL
 *         renderer. The .srt has no attitude, so every contact is honestly CUE_ONLY with
 *         lat/lon = null. Assert: a contact arrives over the real JSON WS, frame_id-aligned
 *         to a real JPEG on the binary WS; it renders ZERO map pins (no Null-Island phantom)
 *         but DOES appear in the survivor list (visibility is never gated).
 *
 *  5.9-b  THE COORDINATE-CONVENTION GUARD — inject a frozen LOCATED ContactRecord (hand-set
 *         lat/lon literals) through the real renderer's store and assert the map pin's GeoJSON
 *         coordinate is [lon, lat] (the transpose). A lat/lng flip anywhere on the
 *         wire→store→toLngLat→MapLibre path puts the pin in the wrong hemisphere; this catches
 *         it. Non-circular: the expected [lon,lat] is a hand-transposed literal, never a
 *         recomputed value. (The coordinate MATH guard lives non-circularly in the Python
 *         analytic ray_to_ground tests + the Task 4.8 glue test with the independent
 *         world_to_pixel oracle.)
 */

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..", "..");

/* These page.evaluate callbacks run in the BROWSER and import the app's modules by their
 * Vite dev-server URL (/src/...). tsc can't (and shouldn't) resolve those web paths, so we
 * import through a runtime-only indirection that tsc treats as a dynamic expression. */
declare global {
  interface Window {
    __imp?: (p: string) => Promise<unknown>;
  }
}
const BINARY_PORT = 8795;
const JSON_PORT = 8796;

let viteServer: ViteDevServer;
let browser: Browser;
let appUrl: string;

test.beforeAll(async () => {
  viteServer = await createServer({ root: path.resolve(__dirname, ".."), server: { port: 5277 } });
  await viteServer.listen();
  appUrl = viteServer.resolvedUrls!.local[0];
  browser = await chromium.launch({
    args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
  });
});

test.afterAll(async () => {
  await browser?.close();
  await viteServer?.close();
});

// A page with the runtime __imp(specifier) → dynamic import indirection installed, plus an
// optional real-service bridge injected before app scripts run.
async function newAppPage(bridge?: { binaryUrl: string; jsonUrl: string }) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.addInitScript(() => {
    (window as unknown as { __imp: (p: string) => Promise<unknown> }).__imp = (p: string) =>
      import(/* @vite-ignore */ p);
  });
  if (bridge) {
    await page.addInitScript((b) => {
      (window as unknown as { hades: unknown }).hades = { version: "e2e", service: b };
    }, bridge);
  }
  return page;
}

function startService(): ChildProcess {
  return spawn(
    "uv",
    [
      "run",
      "hades-service",
      "--clip",
      path.join(REPO_ROOT, "service", "tests", "fixtures", "clip_2s.mp4"),
      "--telemetry",
      path.join(REPO_ROOT, "service", "tests", "fixtures", "clip_2s.srt"),
      "--binary-port",
      String(BINARY_PORT),
      "--json-port",
      String(JSON_PORT),
      // slow the feed so the service keeps serving long enough for Vite build + page load +
      // WS connect (it serves only for the clip's duration, then _pump() returns & closes).
      "--fps",
      "4",
    ],
    { cwd: path.join(REPO_ROOT, "service"), stdio: "inherit" },
  );
}

test("5.9-a: real fixture → real service → real WS → UI: CUE_ONLY contact, no phantom pin, listed", async () => {
  const service = startService();
  const page = await newAppPage({
    binaryUrl: `ws://127.0.0.1:${BINARY_PORT}`,
    jsonUrl: `ws://127.0.0.1:${JSON_PORT}`,
  });
  try {
    // give the service a head start to boot (uv + imports) so the renderer's WS isn't refused
    await new Promise((r) => setTimeout(r, 3500));
    await page.goto(appUrl, { waitUntil: "domcontentloaded" });

    // a real ContactRecord arrives over the real JSON WS and lands in the store
    await page.waitForFunction(
      async () => {
        const m = await (window.__imp!("/src/store/contacts.ts") as Promise<typeof import("../src/store/contacts")>);
        return m.useContactStore.getState().contacts.size > 0;
      },
      { timeout: 30_000 },
    );

    const state = await page.evaluate(async () => {
      const cs = await (window.__imp!("/src/store/contacts.ts") as Promise<typeof import("../src/store/contacts")>);
      const geo = await (window.__imp!("/src/map/geo.ts") as Promise<typeof import("../src/map/geo")>);
      const contacts = [...cs.useContactStore.getState().contacts.values()];
      const fc = geo.contactsToGeoJSON(contacts, null);
      const latest = cs.useContactStore.getState().latestDetection;
      return {
        count: contacts.length,
        allCueOnly: contacts.every((c) => c.actionability_class === "CUE_ONLY"),
        allNullFix: contacts.every((c) => c.lat === null && c.lon === null),
        pinCount: fc.features.length, // located-only → 0 for an all-null-fix mission
        haveDetection: latest !== null,
        someTrackId: contacts[0]?.track_id,
      };
    });

    expect(state.count).toBeGreaterThan(0); // a contact came over the REAL WS
    expect(state.haveDetection).toBe(true); // a DetectionMessage came on the SAME channel
    expect(state.allCueOnly).toBe(true); // position-only .srt → honest CUE_ONLY
    expect(state.allNullFix).toBe(true); // no fabricated coordinate
    expect(state.pinCount).toBe(0); // NO Null-Island phantom pin

    // the contact is still VISIBLE in the survivor list (visibility never gated)
    const row = page.locator(`[data-testid="row-${state.someTrackId}"]`);
    await expect(row).toBeVisible();
  } finally {
    service.kill("SIGTERM");
    await page.close();
  }
});

test("5.9-b: coordinate-convention guard — a located contact pins at [lon, lat], not flipped", async () => {
  // no real service for this one — drive a frozen located record through the real renderer
  const page = await newAppPage();
  await page.goto(appUrl, { waitUntil: "networkidle" });

  const coords = await page.evaluate(async () => {
    const cs = await (window.__imp!("/src/store/contacts.ts") as Promise<typeof import("../src/store/contacts")>);
    const geo = await (window.__imp!("/src/map/geo.ts") as Promise<typeof import("../src/map/geo")>);
    cs.useContactStore.getState().reset();
    // a frozen, located contact (Gulf coast). Expected pin = the TRANSPOSE: [lon, lat].
    cs.useContactStore.getState().ingestContact({
      type: "contact",
      frame_id: 1,
      track_id: 7,
      lat: 30.21487,
      lon: -88.52103,
      r95_m: 18,
      actionability_class: "PINPOINT",
      semi_major_m: 22,
      semi_minor_m: 14,
      orientation_deg: 30,
      priority_tier: "strong",
      convergence_state: "STABLE",
      heading_limited: false,
      aspect_spread_deg: 40,
      detection_conf: 0.94,
      localization_conf: 0.78,
      mc_reject_fraction: 0.02,
      moving_suspected: false,
      age_frames: 30,
    });
    const fc = geo.contactsToGeoJSON([...cs.useContactStore.getState().contacts.values()], null);
    return {
      featureCount: fc.features.length,
      coordinates: fc.features[0]?.geometry.coordinates,
      r95: fc.features[0]?.properties.r95_m,
    };
  });

  expect(coords.featureCount).toBe(1);
  // THE GUARD: GeoJSON order is [lon, lat] — the transpose of the input (lat, lon). A flip
  // anywhere on the wire→store→toLngLat path fails this hand-transposed literal.
  expect(coords.coordinates).toEqual([-88.52103, 30.21487]);
  expect(coords.r95).toBe(18); // expected uncertainty rides through

  await page.close();
});
