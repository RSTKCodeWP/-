// Preload bridge (Task 5.9). Exposes the localhost WS ports the Electron main process started
// the Python `hades-service` on, plus a flag so the renderer knows it's running inside Electron
// (real-service mode) vs. a plain browser/dev (mock mode). The renderer opens the WebSockets
// itself (Chromium can reach localhost directly); main owns the service child's lifecycle.
import { contextBridge } from "electron";

const binaryPort = Number(process.env.HADES_BINARY_PORT ?? 8765);
const jsonPort = Number(process.env.HADES_JSON_PORT ?? 8766);

contextBridge.exposeInMainWorld("hades", {
  version: "0.1.0",
  // present only under Electron → the renderer connects to the real service
  service: {
    binaryUrl: `ws://127.0.0.1:${binaryPort}`,
    jsonUrl: `ws://127.0.0.1:${jsonPort}`,
  },
});
