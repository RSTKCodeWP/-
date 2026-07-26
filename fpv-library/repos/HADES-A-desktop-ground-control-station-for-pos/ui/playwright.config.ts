import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  // One retry: the WebGL-heavy specs (map/latency/demo) run under swiftshader in a single
  // process; cumulative GPU+network-service pressure can crash the GPU process mid-run (the
  // latency spec, which needs an unstarved GL context to capture 20 frames, is the canary). A
  // real assertion regression still fails both attempts — this only absorbs the environmental
  // GPU-process crash, it does not mask product failures.
  retries: 1,
  workers: 1,
  reporter: "list",
  timeout: 30_000,
});
