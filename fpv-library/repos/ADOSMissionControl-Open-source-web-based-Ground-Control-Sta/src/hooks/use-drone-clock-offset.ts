"use client";

import { useEffect, useMemo, useRef } from "react";

import { useAgentConnectionStore } from "@/stores/agent-connection-store";
import { useVideoStore } from "@/stores/video-store";
import { AgentClient } from "@/lib/agent/client";
import { isDemoMode } from "@/lib/utils";

const POLL_INTERVAL_MS = 30_000;
const ROLLING_WINDOW = 5;
const FIRST_PROBE_DELAY_MS = 500;
// After this many ms of consecutive probe failures, clear the offset
// rather than showing a stale value. Two minutes covers a single
// failed poll plus its retry without flashing the row off; anything
// longer is genuinely stale and would feed garbage into G2G math.
const STALENESS_TIMEOUT_MS = 120_000;

interface Sample {
  offsetMs: number;
  uncertaintyMs: number;
}

/**
 * Estimates the drone↔browser wall-clock offset by sampling the
 * agent's /api/time endpoint and applying Cristian's algorithm. The
 * offset is what maps a drone-side SEI timestamp into the browser's
 * own clock for the true glass-to-glass computation.
 *
 * Cristian's algorithm:
 *   t0 = Date.now() before request
 *   t1 = drone's reported time_ns / 1e6
 *   t2 = Date.now() after response
 *   offset      = t1 - (t0 + t2) / 2
 *   uncertainty = (t2 - t0) / 2     (half the round-trip)
 *
 * Polled at 30s; rolling median of last 5 samples filters spikes.
 *
 * In demo mode synthesises a static offset so the breakdown popover
 * row renders during `npm run demo`.
 */
export function useDroneClockOffset(): void {
  const agentUrl = useAgentConnectionStore((s) => s.agentUrl);
  const apiKey = useAgentConnectionStore((s) => s.apiKey);
  const setClockOffset = useVideoStore((s) => s.setClockOffset);

  const demoMode = useMemo(() => isDemoMode(), []);

  const client = useMemo(() => {
    if (demoMode) return null;
    if (!agentUrl) return null;
    return new AgentClient(agentUrl, apiKey);
  }, [agentUrl, apiKey, demoMode]);

  const samplesRef = useRef<Sample[]>([]);
  const lastSuccessAtRef = useRef<number | null>(null);

  useEffect(() => {
    if (demoMode) {
      // Static-with-noise offset so the popover row looks live without
      // hitting the network. Roughly mimics a healthy chrony pair on
      // LAN: ~-7 ms with ±2 ms uncertainty.
      const offset = -7 + Math.sin(Date.now() / 60_000) * 1.5;
      setClockOffset({
        clockOffsetMs: offset,
        clockOffsetUncertaintyMs: 2,
      });
      const id = window.setInterval(() => {
        const next = -7 + Math.sin(Date.now() / 60_000) * 1.5;
        setClockOffset({
          clockOffsetMs: next,
          clockOffsetUncertaintyMs: 2,
        });
      }, POLL_INTERVAL_MS);
      return () => window.clearInterval(id);
    }

    if (!client) return;
    samplesRef.current = [];

    let cancelled = false;

    const probe = async () => {
      const t0 = Date.now();
      try {
        const resp = await client.getTime();
        const t2 = Date.now();
        if (cancelled || !resp || typeof resp.time_ns !== "number") {
          if (!cancelled && resp == null) {
            // Endpoint missing — older agent. Surface null so the
            // popover row hides itself rather than showing stale data.
            setClockOffset({
              clockOffsetMs: null,
              clockOffsetUncertaintyMs: null,
            });
          }
          return;
        }
        const t1Ms = resp.time_ns / 1_000_000;
        const offsetMs = t1Ms - (t0 + t2) / 2;
        const uncertaintyMs = (t2 - t0) / 2;
        samplesRef.current.push({ offsetMs, uncertaintyMs });
        if (samplesRef.current.length > ROLLING_WINDOW) {
          samplesRef.current.shift();
        }
        const sorted = samplesRef.current
          .slice()
          .sort((a, b) => a.offsetMs - b.offsetMs);
        const median = sorted[Math.floor(sorted.length / 2)];
        setClockOffset({
          clockOffsetMs: median.offsetMs,
          clockOffsetUncertaintyMs: median.uncertaintyMs,
        });
        lastSuccessAtRef.current = Date.now();
      } catch {
        if (cancelled) return;
        // Transient failures: keep the last good offset visible
        // rather than blinking the row off. But if every probe in the
        // last STALENESS_TIMEOUT_MS has failed, clear the offset so
        // downstream G2G math doesn't compute against a clock estimate
        // that may have drifted seconds away from reality.
        const lastOk = lastSuccessAtRef.current;
        if (lastOk !== null && Date.now() - lastOk > STALENESS_TIMEOUT_MS) {
          setClockOffset({
            clockOffsetMs: null,
            clockOffsetUncertaintyMs: null,
          });
          samplesRef.current = [];
          lastSuccessAtRef.current = null;
        }
      }
    };

    const firstHandle = window.setTimeout(() => {
      void probe();
    }, FIRST_PROBE_DELAY_MS);
    const intervalHandle = window.setInterval(() => {
      void probe();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearTimeout(firstHandle);
      window.clearInterval(intervalHandle);
    };
  }, [client, demoMode, setClockOffset]);
}
