/// <reference types="vite/client" />

import type { LauncherApi } from '../shared/ipc-channels.js';

declare global {
  interface Window {
    launcher: LauncherApi;
  }
}

export {};
