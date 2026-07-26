import { useEffect, useState } from 'react';
import type { InstallPhase } from '../../../shared/script-installer-types';

/**
 * Subscribe to install state push events from the main process.
 * Returns the latest phase, or null before any events have arrived.
 */
export function useInstallerState(): InstallPhase | null {
  const [phase, setPhase] = useState<InstallPhase | null>(null);

  useEffect(() => {
    const api = window.electronAPI;
    if (!api?.onScriptInstallerState) return;
    const unsubscribe = api.onScriptInstallerState((next) => {
      setPhase(next as InstallPhase);
    });
    return unsubscribe;
  }, []);

  return phase;
}
