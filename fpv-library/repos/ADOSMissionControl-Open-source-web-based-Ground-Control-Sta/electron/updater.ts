import { BrowserWindow, ipcMain } from "electron";
import { autoUpdater } from "electron-updater";

/** Setup auto-updater with GitHub Releases. */
export function setupAutoUpdater(win: BrowserWindow): void {
  // Don't auto-download — let the user decide
  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = true;

  // Suppress errors in dev (no published releases to check)
  autoUpdater.logger = null;

  autoUpdater.on("update-available", (info) => {
    if (!win.isDestroyed()) {
      win.webContents.send("update-available", { version: info.version });
    }
  });

  autoUpdater.on("update-downloaded", (info) => {
    if (!win.isDestroyed()) {
      win.webContents.send("update-downloaded", { version: info.version });
    }
  });

  // IPC handler for user-triggered install
  ipcMain.handle("update:install", () => {
    autoUpdater.quitAndInstall();
  });

  // Check for updates silently on startup (ignore errors)
  autoUpdater.checkForUpdates().catch(() => {});
}
