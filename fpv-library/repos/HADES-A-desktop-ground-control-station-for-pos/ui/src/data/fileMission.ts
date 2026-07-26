import { useEffect } from "react";

import { videoFrameSink } from "../components/VideoPanel";
import { useAlertStore } from "../store/alerts";
import { useContactStore } from "../store/contacts";
import { useMissionLog } from "../store/missionLog";
import { useProvenanceStore } from "../store/provenance";
import { useSystemStore } from "../store/system";
import { useTelemetryStore } from "../store/telemetry";
import { MockWsServer } from "../mock/mock-ws";
import { commandSink } from "../ws/commandSink";
import { loadMission, type BakedMission } from "./mission";

/* Phase 6 — the browser FILE-mission source. It replays a baked `mission.json` through the SAME
 * stores the live service feeds, so the entire UI is reused; only the source swaps. It is built
 * on the EXISTING `MockWsServer` (which already replays frames+json on a timer, frame_id-keyed)
 * rather than a new transport — the only file-source specifics are: (1) provenance for the demo
 * banner, (2) a scripted LINK-LOST window driven from the baked timeline (not a fake socket
 * drop), and (3) a promote handler that swaps in the baked REFINED record so the contact visibly
 * tightens — the honest replay of on-demand fusion (there is no Python fuser in the demo). */

export interface WireOptions {
  intervalMs?: number;
}

/** Wire a parsed baked mission to the stores via a `MockWsServer` and play it. Returns a stop
 * fn. Awaitable: resolves after the replay finishes (so tests can assert the end-state). The
 * mission clock is the baked epoch + frame timestamp — a truthful clock, not `Date.now()`. */
export async function wireMission(mission: BakedMission, opts: WireOptions = {}): Promise<() => void> {
  const server = new MockWsServer({
    frames: mission.frames,
    json: mission.json,
    intervalMs: opts.intervalMs ?? 33,
  });

  useProvenanceStore.getState().setProvenance(mission.provenance);

  const missionClock = (frameId: number) => mission.missionEpochMs + frameId * 33;

  const frameSink = (f: typeof mission.frames[number]) => {
    videoFrameSink.push(f);
    useSystemStore.getState().markFrame(f.frame_id); // heartbeat bound to frame arrival

    // scripted LINK-LOST window (degrade-visibly demo moment) — driven from the baked timeline,
    // never a faked socket drop. Down inside [from, to), recovered after.
    const { fromFrame, toFrame } = mission.linkLost;
    const sys = useSystemStore.getState();
    const shouldBeUp = !(f.frame_id >= fromFrame && f.frame_id < toFrame);
    if (sys.linkUp !== shouldBeUp) {
      sys.setLink(shouldBeUp);
      if (!shouldBeUp) {
        useMissionLog.getState().append({ kind: "link", text: "LINK LOST", t: missionClock(f.frame_id) });
      }
    }

    // synthesize a drone track + sweeping footprint so the map context layers populate (the
    // baked stream carries contacts/detections, not raw pose). The track sweeps ACROSS the
    // baked survivor area (~30.2150, -88.5200) so the camera footprint sits under the pins and
    // the geometry reads as coherent — a flying-over sweep, not a decoupled wash.
    const t = f.frame_id;
    const lat = 30.2128 + t * 0.00005; // climbs north through the survivors near mid-mission
    const lon = -88.5208 + t * 0.00002;
    const tel = useTelemetryStore.getState();
    tel.pushPose({ lat, lon, heading_deg: 20, agl_m: 40 });
    const d = 0.0007;
    tel.setFootprint([
      [lon - d, lat - d],
      [lon + d, lat - d],
      [lon + d, lat + d],
      [lon - d, lat + d],
    ]);
    sys.setTelemetryAge(0.2);
    sys.setGps("3d", 11);
  };
  const offFrame = server.onFrame(frameSink);

  const seen = new Set<number>();
  const offJson = server.onJson((m) => {
    useContactStore.getState().ingestJson(m);
    if (m.type === "contact" && !seen.has(m.track_id)) {
      seen.add(m.track_id);
      useAlertStore.getState().consider(m);
      useMissionLog.getState().append({
        kind: "detection",
        text: `trk ${m.track_id} NEW ${m.actionability_class}`,
        t: missionClock(m.frame_id),
      });
    } else if (m.type === "contact") {
      useAlertStore.getState().consider(m);
    }
  });

  // operator-promote → swap in the baked REFINED record (honest on-demand-fusion replay) + log.
  // No Python fuser in the demo; the refined record was produced by the real fuser at bake time.
  commandSink.setHandler((trackId) => {
    const refined = mission.promoteRefined;
    if (refined && refined.track_id === trackId) {
      useContactStore.getState().ingestContact(refined);
    }
    useMissionLog.getState().append({
      kind: "note",
      text: `trk ${trackId} promote → fuse (demo)`,
      t: missionClock(refined?.frame_id ?? 0),
    });
  });

  await server.play();

  return () => {
    commandSink.setHandler(null);
    server.stop();
    offFrame();
    offJson();
  };
}

/** Hook form: fetch the baked mission and replay it, paced for a believable live feel. Falls
 * back to nothing if the artifact is absent (the caller decides the synthetic fallback). */
export function useFileMission(enabled = true): void {
  useEffect(() => {
    if (!enabled) return;
    let stop: (() => void) | null = null;
    let cancelled = false;
    void loadMission().then((mission) => {
      if (cancelled || !mission) return;
      void wireMission(mission, { intervalMs: 33 }).then((s) => {
        if (cancelled) s();
        else stop = s;
      });
    });
    return () => {
      cancelled = true;
      stop?.();
    };
  }, [enabled]);
}
