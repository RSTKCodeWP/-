import { spawn, type ChildProcess } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { app, BrowserWindow } from "electron";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/* Electron main (Task 5.9): supervises the Python `hades-service` child and serves the
 * renderer. The service streams two localhost WS channels (binary 8765 / JSON 8766) that the
 * renderer connects to directly (preload exposes the ports). v1 spawns the dev `uv run`
 * service; PyInstaller bundling is M9/v1.x. Env vars let the E2E harness point the renderer at
 * an externally-started service instead (HADES_NO_SPAWN=1). */

const BINARY_PORT = Number(process.env.HADES_BINARY_PORT ?? 8765);
const JSON_PORT = Number(process.env.HADES_JSON_PORT ?? 8766);
let service: ChildProcess | null = null;

function repoRoot(): string {
  // dist-electron/main.js → ui/ → repo root
  return path.resolve(__dirname, "..", "..");
}

function startService(): void {
  if (process.env.HADES_NO_SPAWN === "1") return; // E2E supplies its own service
  const root = repoRoot();
  const clip = process.env.HADES_CLIP ?? path.join(root, "service", "tests", "fixtures", "clip_2s.mp4");
  const srt = process.env.HADES_SRT ?? path.join(root, "service", "tests", "fixtures", "clip_2s.srt");
  service = spawn(
    "uv",
    [
      "run",
      "hades-service",
      "--clip",
      clip,
      "--telemetry",
      srt,
      "--binary-port",
      String(BINARY_PORT),
      "--json-port",
      String(JSON_PORT),
    ],
    { cwd: path.join(root, "service"), stdio: "inherit" },
  );
  service.on("exit", (code) => {
    if (code && code !== 0) console.error(`hades-service exited with code ${code}`);
  });
}

function stopService(): void {
  service?.kill("SIGTERM");
  service = null;
}

function createWindow(): void {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1280,
    minHeight: 800,
    backgroundColor: "#0B0E14", // --bg-base
    show: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.mjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const devServerUrl = process.env.VITE_DEV_SERVER_URL;
  if (devServerUrl) {
    void win.loadURL(devServerUrl);
  } else {
    void win.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

app.whenReady().then(() => {
  startService();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  stopService();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", stopService);
