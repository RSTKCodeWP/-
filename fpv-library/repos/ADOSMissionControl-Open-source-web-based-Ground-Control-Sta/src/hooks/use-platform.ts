"use client";

import { useState, useLayoutEffect } from "react";

export function usePlatform() {
  const [state, setState] = useState({
    isElectron: false,
    platform: null as string | null,
    isMac: false,
    isWindows: false,
    isLinux: false,
  });

  useLayoutEffect(() => {
    const api = window.electronAPI;
    if (api?.isElectron) {
      setState({
        isElectron: true,
        platform: api.platform,
        isMac: api.platform === "darwin",
        isWindows: api.platform === "win32",
        isLinux: api.platform === "linux",
      });
    }
  }, []);

  return state;
}
