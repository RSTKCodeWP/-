"use client";

/**
 * Sync the cloud key row presence + operator's cloud-sync intent for the
 * given drone. Intent persists across sessions via signing-prefs; row
 * presence comes from a Convex lookup. The two can disagree: operator
 * opts in -> intent=true, no row yet. After first rotation -> both true.
 *
 * Returns the pair plus setters so the parent panel's event handlers
 * (toggle, rotate, disable) can update them after async operations.
 *
 * @module components/fc/security/signing/use-cloud-row-sync
 */

import { useEffect, useState } from "react";
import type { ConvexReactClient } from "convex/react";
import { getCloudKeyForDrone } from "@/lib/api/signing-cloud-sync";
import { getPrefs } from "@/lib/protocol/signing-prefs";

export interface CloudRowSync {
  cloudRowPresent: boolean;
  cloudSyncIntent: boolean;
  setCloudRowPresent: (v: boolean) => void;
  setCloudSyncIntent: (v: boolean) => void;
}

export function useCloudRowSync(
  droneId: string,
  convexClient: ConvexReactClient | undefined,
  isAuthenticated: boolean,
): CloudRowSync {
  const [cloudRowPresent, setCloudRowPresent] = useState(false);
  const [cloudSyncIntent, setCloudSyncIntent] = useState(false);

  // Preserves the original SigningPanel behavior: when droneId is empty,
  // reset the local state. The async branch is scheduled regardless of the
  // auth/convex availability — it just short-circuits without a Convex read.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (!droneId) {
      setCloudRowPresent(false);
      setCloudSyncIntent(false);
      return;
    }
    let cancelled = false;
    (async () => {
      const prefs = await getPrefs(droneId);
      if (!cancelled) setCloudSyncIntent(prefs.cloudSyncIntent);
      if (!isAuthenticated || !convexClient) {
        if (!cancelled) setCloudRowPresent(false);
        return;
      }
      try {
        const row = await getCloudKeyForDrone(convexClient, droneId);
        if (!cancelled) setCloudRowPresent(row !== null);
      } catch {
        if (!cancelled) setCloudRowPresent(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [droneId, isAuthenticated, convexClient]);
  /* eslint-enable react-hooks/set-state-in-effect */

  return { cloudRowPresent, cloudSyncIntent, setCloudRowPresent, setCloudSyncIntent };
}
