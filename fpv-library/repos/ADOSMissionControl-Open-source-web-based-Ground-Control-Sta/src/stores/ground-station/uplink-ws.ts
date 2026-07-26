/**
 * Uplink WebSocket event handler. Lifted out of `uplink-store.ts` so the
 * slice file stays focused on REST actions.
 *
 * @license GPL-3.0-only
 */

import { FAILOVER_LOG_CAP } from "./initial-state";
import type { GroundStationState } from "./state";
import type {
  GroundStationApi,
  UplinkEvent,
  UplinkFailoverEntry,
  UplinkHealth,
} from "@/lib/api/ground-station-api";

export function subscribeUplinkWs(
  api: GroundStationApi,
  set: (
    partial:
      | Partial<GroundStationState>
      | ((s: GroundStationState) => Partial<GroundStationState>),
  ) => void,
  get: () => GroundStationState,
): () => void {
  return api.subscribeUplinkEvents((event: UplinkEvent) => {
    const current = get().uplink;
    if (event.type === "state") {
      const e = event as {
        active?: string | null;
        priority?: string[];
        health?: UplinkHealth;
      };
      set({
        uplink: {
          ...current,
          active: e.active ?? current.active,
          priority: e.priority ?? current.priority,
          health: e.health ?? current.health,
        },
      });
    } else if (event.type === "active") {
      const e = event as { iface: string };
      set({ uplink: { ...current, active: e.iface } });
    } else if (event.type === "priority") {
      const e = event as { priority: string[] };
      set({ uplink: { ...current, priority: e.priority } });
    } else if (event.type === "health") {
      const e = event as { health: UplinkHealth };
      set({ uplink: { ...current, health: e.health } });
    } else if (event.type === "failover") {
      const e = event as {
        from: string | null;
        to: string;
        reason: string;
        timestamp?: number;
      };
      const entry: UplinkFailoverEntry = {
        from: e.from,
        to: e.to,
        reason: e.reason,
        timestamp: e.timestamp ?? Date.now(),
      };
      const nextLog = [entry, ...current.failover_log].slice(0, FAILOVER_LOG_CAP);
      set({
        uplink: {
          ...current,
          active: e.to,
          failover_log: nextLog,
        },
      });
    } else if (event.type === "data_cap") {
      const e = event as {
        state: "ok" | "warn_80" | "throttle_95" | "blocked_100";
        percent: number;
        used_mb: number;
        cap_mb: number;
      };
      set({
        uplink: {
          ...current,
          data_cap: {
            state: e.state,
            percent: e.percent,
            used_mb: e.used_mb,
            cap_mb: e.cap_mb,
          },
        },
      });
    }
  });
}
