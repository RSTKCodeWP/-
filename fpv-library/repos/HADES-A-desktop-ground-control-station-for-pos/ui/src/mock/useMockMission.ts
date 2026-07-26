import { useEffect } from "react";

import { videoFrameSink } from "../components/VideoPanel";
import { useAlertStore } from "../store/alerts";
import { useContactStore } from "../store/contacts";
import { useMissionLog } from "../store/missionLog";
import { useSystemStore } from "../store/system";
import { useTelemetryStore } from "../store/telemetry";
import { commandSink } from "../ws/commandSink";
import { cannedMission } from "./cannedMission";
import { MockWsServer } from "./mock-ws";

/* Plays the canned mission through the same two-channel shape the real service uses
 * (impl-plan Task 5.1) so the whole UI runs offline + deterministic before the real Python
 * service is wired (5.9). Frames → the video sink + the heartbeat; JSON → the contact store;
 * a synthetic drone track → the telemetry store so the map's non-pin layers populate. */

export function useMockMission(enabled = true): void {
  useEffect(() => {
    if (!enabled) return;
    const { frames, json } = cannedMission();
    const server = new MockWsServer({ frames, json, intervalMs: 33 });

    const offFrame = server.onFrame((f) => {
      videoFrameSink.push(f);
      useSystemStore.getState().markFrame(f.frame_id); // heartbeat is bound to frame arrival
      // synthesize a drone track + sweeping footprint so the map context layers populate
      const t = f.frame_id;
      const lat = 30.211 + t * 0.00006;
      const lon = -88.526 + t * 0.00004;
      const tel = useTelemetryStore.getState();
      tel.pushPose({ lat, lon, heading_deg: 34, agl_m: 30 });
      const d = 0.0009;
      tel.setFootprint([
        [lon - d, lat - d],
        [lon + d, lat - d],
        [lon + d, lat + d],
        [lon - d, lat + d],
      ]);
      useSystemStore.getState().setTelemetryAge(0.2);
      useSystemStore.getState().setGps("3d", 11);
    });
    const seen = new Set<number>();
    const offJson = server.onJson((m) => {
      const store = useContactStore.getState();
      store.ingestJson(m);
      if (m.type === "contact") {
        useAlertStore.getState().consider(m); // rationed loud alert
        if (!seen.has(m.track_id)) {
          seen.add(m.track_id);
          useMissionLog.getState().append({
            kind: "detection",
            text: `trk ${m.track_id} NEW ${m.actionability_class}`,
            t: Date.UTC(2026, 5, 25, 14, 22, 0) + m.frame_id * 33, // synthetic mission clock
          });
        }
      }
    });

    // mock has no Python fuser to re-run; record the operator's promote so the action is
    // observable in demo mode (the real service returns a refined record — see useRealService).
    commandSink.setHandler((trackId) =>
      useMissionLog.getState().append({
        kind: "note",
        text: `trk ${trackId} promote → fuse (demo)`,
        t: Date.now(),
      }),
    );

    void server.play();
    return () => {
      commandSink.setHandler(null);
      server.stop();
      offFrame();
      offJson();
    };
  }, [enabled]);
}
