/**
 * @module INavMissionPanel
 * @description iNav mission summary panel.
 * Read-only overview of the current mission loaded in the mission store.
 * Counts waypoints, breaks down by action type, and points the operator
 * at the mission planner tab for edits. Full mission editing lives in the
 * planner, not here.
 * @license GPL-3.0-only
 */

"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMissionStore } from "@/stores/mission-store";
import { useDroneManager } from "@/stores/drone-manager";
import { PanelHeader } from "../shared/PanelHeader";
import { Route, ArrowRight } from "lucide-react";
import { INAV_WP_ACTION } from "@/lib/protocol/msp/msp-decoders-inav";

// ── Action label map ──────────────────────────────────────────

const ACTION_LABELS: Record<number, string> = {
  [INAV_WP_ACTION.WAYPOINT]: "Waypoint",
  [INAV_WP_ACTION.POSHOLD_UNLIM]: "Position hold (unlimited)",
  [INAV_WP_ACTION.POSHOLD_TIME]: "Position hold (timed)",
  [INAV_WP_ACTION.RTH]: "Return to home",
  [INAV_WP_ACTION.SET_POI]: "Set point of interest",
  [INAV_WP_ACTION.JUMP]: "Jump",
  [INAV_WP_ACTION.SET_HEAD]: "Set heading",
  [INAV_WP_ACTION.LAND]: "Land",
};

// ── Component ─────────────────────────────────────────────────

export function INavMissionPanel() {
  const router = useRouter();
  const getSelectedProtocol = useDroneManager((s) => s.getSelectedProtocol);
  const waypoints = useMissionStore((s) => s.waypoints);
  const setWaypoints = useMissionStore((s) => s.setWaypoints);
  const connected = !!getSelectedProtocol();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasRead, setHasRead] = useState(false);

  const summary = useMemo(() => {
    const counts: Record<number, number> = {};
    for (const wp of waypoints) {
      const action = (wp as { inavAction?: number }).inavAction ?? INAV_WP_ACTION.WAYPOINT;
      counts[action] = (counts[action] ?? 0) + 1;
    }
    return counts;
  }, [waypoints]);

  const handleRead = useCallback(async () => {
    const protocol = getSelectedProtocol();
    if (!protocol) {
      setError("No drone connected");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const items = await protocol.downloadMission();
      // downloadMission returns MAVLink MissionItem shape; mission-store expects Waypoint shape.
      // Translate to Waypoint-compatible objects for display purposes only.
      const waypointRecords = items.map((it, i) => ({
        id: `fc-${i}`,
        seq: i,
        lat: it.x / 1e7,
        lon: it.y / 1e7,
        alt: it.z,
        command: it.command,
        param1: it.param1,
        param2: it.param2,
        param3: it.param3,
        param4: it.param4,
        frame: it.frame,
        autocontinue: it.autocontinue === 1,
      }));
      setWaypoints(waypointRecords as unknown as Parameters<typeof setWaypoints>[0]);
      setHasRead(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [getSelectedProtocol, setWaypoints]);

  const handleOpenPlanner = useCallback(() => {
    router.push("/plan");
  }, [router]);

  // hasLoaded reflects whether we have mission data to summarize, either from a
  // local plan or from a Read-from-FC pull. Avoids the previous always-true stub.
  const hasLoaded = hasRead || waypoints.length > 0;

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl space-y-4">
        <PanelHeader
          title="iNav Mission"
          subtitle="Summary of the mission in the Plan tab or read from the FC."
          icon={<Route size={16} />}
          loading={loading}
          loadProgress={null}
          hasLoaded={hasLoaded}
          onRead={handleRead}
          connected={connected}
          error={error}
        />

        <div className="border border-border-default rounded p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-text-secondary">Total waypoints</span>
            <span className="text-[14px] font-mono text-text-primary">{waypoints.length} / 60</span>
          </div>

          {waypoints.length === 0 ? (
            <p className="text-[11px] text-text-tertiary">
              No mission loaded. Open the Plan tab to build one.
            </p>
          ) : (
            <div className="space-y-1">
              <span className="text-[10px] text-text-tertiary font-mono">Breakdown by action</span>
              {Object.entries(summary).map(([actionId, count]) => (
                <div key={actionId} className="flex items-center justify-between text-[11px]">
                  <span className="text-text-secondary">
                    {ACTION_LABELS[parseInt(actionId)] ?? `Action ${actionId}`}
                  </span>
                  <span className="font-mono text-text-primary">{count}</span>
                </div>
              ))}
            </div>
          )}

          <div className="pt-2 border-t border-border-default">
            <button
              type="button"
              onClick={handleOpenPlanner}
              className="flex items-center gap-2 text-[11px] px-3 py-1 border border-accent-primary text-accent-primary rounded hover:bg-accent-primary/10"
            >
              Open Mission Planner
              <ArrowRight size={12} />
            </button>
          </div>
        </div>

        <div className="border border-border-default rounded p-4 space-y-2">
          <span className="text-[10px] text-text-tertiary font-mono">iNav waypoint actions</span>
          <p className="text-[11px] text-text-secondary">
            iNav supports eight waypoint action types. Use the action dropdown in the Plan tab
            to pick non-default actions (Jump, Set heading, Set POI, Poshold timed, Land).
          </p>
        </div>
      </div>
    </div>
  );
}
