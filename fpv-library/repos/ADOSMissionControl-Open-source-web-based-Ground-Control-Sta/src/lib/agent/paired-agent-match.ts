/**
 * @module paired-agent-match
 * @description Decide whether a connection URL points at a paired LAN agent's
 * own host. A paired agent's flight controller is reached over MAVLink by its
 * agent bridge (which owns the `node:<deviceId>` fleet card); a SECOND, direct
 * connection to the same host (auto-reconnect of a saved `ws://<agent>:8765`,
 * a "Reconnect" of a recent entry) would spawn a duplicate standalone card.
 * Callers use this to skip such direct dials and let the agent bridge own the FC.
 *
 * @license GPL-3.0-only
 */

import { useLocalNodesStore } from "@/stores/local-nodes-store";

/** Lower-cased hostname of a URL or bare host string, or null if unparseable. */
function hostOf(urlOrHost: string | undefined | null): string | null {
  let s = (urlOrHost ?? "").trim();
  if (!s) return null;
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(s)) s = `http://${s}`;
  try {
    return new URL(s).hostname.toLowerCase();
  } catch {
    return null;
  }
}

/** The deviceId of a paired local agent whose hostname / mDNS name / IPv4
 * matches the host of `url`, or null when the URL is not a paired agent. */
export function pairedAgentDeviceIdForUrl(url: string): string | null {
  const host = hostOf(url);
  if (!host) return null;
  for (const n of useLocalNodesStore.getState().nodes) {
    const candidates = [
      hostOf(n.hostname),
      hostOf(n.mdnsHost),
      n.ipv4 ? n.ipv4.toLowerCase() : null,
    ];
    if (candidates.includes(host)) return n.deviceId;
  }
  return null;
}
