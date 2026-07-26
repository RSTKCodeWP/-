/**
 * @module ResolveLanUrl
 * @description Local copy of the LAN URL resolver used by the plugin
 * install dialog. Mirrors the resolver in
 * `src/stores/agent-connection/cloud-state.ts` exactly; duplicated here
 * to avoid reaching into another domain's store internals from the
 * dialog. Keep the two in sync if either changes.
 *
 * On HTTPS origins the browser blocks plain-HTTP fetches to a private
 * LAN host (mixed content). Returning `null` here lets the cloud-relay
 * path take over cleanly rather than the dialog surfacing a "Failed to
 * fetch" against a doomed direct call.
 *
 * Also returns the paired API key so the dialog can stamp the
 * `X-ADOS-Key` header without prompting.
 *
 * @license GPL-3.0-only
 */

import { useLocalNodesStore } from "@/stores/local-nodes-store";
import { usePairingStore } from "@/stores/pairing-store";

export interface LanTarget {
  url: string;
  apiKey: string;
}

export function resolveLanTarget(deviceId: string): LanTarget | null {
  if (
    typeof window !== "undefined" &&
    window.location.protocol === "https:"
  ) {
    return null;
  }
  const url = pickUrl(deviceId);
  const apiKey = pickKey(deviceId);
  if (!url || !apiKey) return null;
  return { url, apiKey };
}

function pickUrl(deviceId: string): string | null {
  const localNode = useLocalNodesStore
    .getState()
    .nodes.find((n) => n.deviceId === deviceId);
  if (localNode) {
    if (localNode.hostname) return localNode.hostname;
    const host = localNode.mdnsHost || localNode.ipv4;
    if (host) return `http://${host}:8080`;
  }
  const pairedDrone = usePairingStore
    .getState()
    .pairedDrones.find((d) => d.deviceId === deviceId);
  if (pairedDrone) {
    const host = pairedDrone.mdnsHost || pairedDrone.lastIp;
    if (host) return `http://${host}:8080`;
  }
  return null;
}

function pickKey(deviceId: string): string | null {
  const localNode = useLocalNodesStore
    .getState()
    .nodes.find((n) => n.deviceId === deviceId);
  if (localNode?.apiKey) return localNode.apiKey;
  const pairedDrone = usePairingStore
    .getState()
    .pairedDrones.find((d) => d.deviceId === deviceId);
  return pairedDrone?.apiKey ?? null;
}
