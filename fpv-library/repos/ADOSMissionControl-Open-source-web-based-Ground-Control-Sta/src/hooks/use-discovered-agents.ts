/**
 * @module useDiscoveredAgents
 * @description Polls the LAN for unpaired ADOS agents and populates
 * ``pairing-store.discoveredAgents``. Discovery runs server-side via
 * ``/api/lan-pair/discover`` (Node mDNS over ``bonjour-service``), and
 * each candidate host is probed through ``/api/lan-pair/probe`` for its
 * identity and current pair code.
 *
 * Routing both calls through Mission Control's own Next.js server means
 * this works the same in the browser GCS, the desktop build, and
 * self-hosted deployments: the Node side resolves ``*.local`` via the OS
 * resolver and sidesteps HTTPS mixed-content. Inside Docker without host
 * networking the mDNS scan returns nothing and the list stays empty.
 *
 * Wire contract: discover returns ``{ agents: [{ host, ipv4, port, txt }] }``;
 * each host is probed for ``device_id / name / board / version /
 * pairing_code / paired / mdns_host``. Agents reporting ``paired === true``
 * are filtered out since they are already owned.
 * @license GPL-3.0-only
 */

import { useEffect, useRef } from "react";
import { isDemoMode } from "@/lib/utils";
import {
  usePairingStore,
  type DiscoveredAgent,
} from "@/stores/pairing-store";

const POLL_INTERVAL_MS = 5000;
const DISCOVER_TIMEOUT_MS = 5000;
const PROBE_TIMEOUT_MS = 4000;

interface LanDiscoveredAgent {
  host: string;
  ipv4?: string;
  port: number;
  txt: Record<string, string>;
}

interface ProbeInfo {
  device_id?: string;
  name?: string;
  board?: string;
  version?: string;
  pairing_code?: string | null;
  paired?: boolean;
  mdns_host?: string;
  ipv4?: string;
}

/** Scan the LAN for unpaired agents and resolve each to a full identity.
 *  An mDNS record can carry a stale IPv4 while the hostname still
 *  resolves (or vice versa), so both targets are probed per agent and
 *  the results are deduped by device id. */
async function discoverUnpaired(
  signal: AbortSignal,
): Promise<DiscoveredAgent[]> {
  const discoverResp = await fetch("/api/lan-pair/discover", {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!discoverResp.ok) return [];
  const { agents } = (await discoverResp.json()) as {
    agents?: LanDiscoveredAgent[];
  };
  if (!agents || agents.length === 0) return [];

  const targets: string[] = [];
  for (const a of agents) {
    if (a.host) targets.push(a.host);
    if (a.ipv4) targets.push(a.ipv4);
  }

  const probes = targets.map(async (target): Promise<ProbeInfo | null> => {
    try {
      const resp = await fetch("/api/lan-pair/probe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ host: target }),
        signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
      });
      if (!resp.ok) return null;
      return (await resp.json()) as ProbeInfo;
    } catch {
      return null;
    }
  });
  const infos = await Promise.all(probes);

  const byDeviceId = new Map<string, DiscoveredAgent>();
  for (const info of infos) {
    if (!info || !info.device_id) continue;
    if (info.paired) continue;
    if (byDeviceId.has(info.device_id)) continue;
    byDeviceId.set(info.device_id, {
      deviceId: info.device_id,
      name: info.name || "ADOS Agent",
      board: info.board || "unknown",
      version: info.version || "",
      pairingCode: info.pairing_code || "",
      mdnsHost: info.mdns_host || "",
      localIp: info.ipv4 || undefined,
    });
  }
  return Array.from(byDeviceId.values());
}

export function useDiscoveredAgents(): void {
  const setDiscoveredAgents = usePairingStore((s) => s.setDiscoveredAgents);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    // Demo mode has no real agents to find; skip the network scan.
    if (isDemoMode()) {
      return () => {
        mountedRef.current = false;
      };
    }

    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const poll = async () => {
      if (cancelled || !mountedRef.current) return;
      try {
        const agents = await discoverUnpaired(
          AbortSignal.timeout(DISCOVER_TIMEOUT_MS),
        );
        if (cancelled || !mountedRef.current) return;
        setDiscoveredAgents(agents);
      } catch {
        if (cancelled || !mountedRef.current) return;
        setDiscoveredAgents([]);
      }
    };

    void poll();
    timer = setInterval(() => void poll(), POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      mountedRef.current = false;
      if (timer) clearInterval(timer);
    };
  }, [setDiscoveredAgents]);
}
