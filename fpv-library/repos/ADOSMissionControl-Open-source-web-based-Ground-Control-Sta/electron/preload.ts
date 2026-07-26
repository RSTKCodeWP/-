import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electronAPI", {
  isElectron: true,
  platform: process.platform,

  // App info
  getVersion: () => ipcRenderer.invoke("app:version"),

  // Window controls (for custom title bar if needed)
  minimize: () => ipcRenderer.invoke("window:minimize"),
  maximize: () => ipcRenderer.invoke("window:maximize"),
  close: () => ipcRenderer.invoke("window:close"),

  // Auto-update
  onUpdateAvailable: (callback: (info: { version: string }) => void) => {
    ipcRenderer.on("update-available", (_event, info) => callback(info));
  },
  onUpdateDownloaded: (callback: (info: { version: string }) => void) => {
    ipcRenderer.on("update-downloaded", (_event, info) => callback(info));
  },
  installUpdate: () => ipcRenderer.invoke("update:install"),

  // Native UDP/TCP MAVLink sockets (the browser sandbox can't open raw sockets).
  net: {
    open: (spec: {
      proto: "udp" | "tcp";
      host: string;
      port: number;
      mode?: "listen" | "target";
    }) => ipcRenderer.invoke("net:open", spec),
    send: (id: string, data: Uint8Array) =>
      ipcRenderer.invoke("net:send", id, data),
    close: (id: string) => ipcRenderer.invoke("net:close", id),
    onData: (callback: (msg: { id: string; data: Uint8Array }) => void) => {
      const handler = (_e: unknown, msg: { id: string; data: Uint8Array }) =>
        callback(msg);
      ipcRenderer.on("net:data", handler);
      return () => ipcRenderer.removeListener("net:data", handler);
    },
    onClose: (callback: (msg: { id: string; reason?: string }) => void) => {
      const handler = (_e: unknown, msg: { id: string; reason?: string }) =>
        callback(msg);
      ipcRenderer.on("net:close", handler);
      return () => ipcRenderer.removeListener("net:close", handler);
    },
  },
});
