"use client";

/**
 * Detect private-browsing mode once per mount. The answer doesn't change
 * during a session, so no need to re-run.
 *
 * @module components/fc/security/signing/use-private-browsing-detection
 */

import { useEffect, useState } from "react";
import { detectPrivateBrowsing } from "@/lib/protocol/private-browsing";

export function usePrivateBrowsingDetection(): boolean {
  const [privateBrowsing, setPrivateBrowsing] = useState(false);
  useEffect(() => {
    let cancelled = false;
    detectPrivateBrowsing().then((v) => {
      if (!cancelled) setPrivateBrowsing(v);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return privateBrowsing;
}
