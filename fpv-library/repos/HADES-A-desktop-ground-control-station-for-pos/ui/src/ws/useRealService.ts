import { useEffect } from "react";

import { videoFrameSink } from "../components/VideoPanel";
import { useAlertStore } from "../store/alerts";
import { useContactStore } from "../store/contacts";
import { useMissionLog } from "../store/missionLog";
import { useSystemStore } from "../store/system";
import { commandSink } from "./commandSink";
import { RealWsClient } from "./realWsClient";

/* Connects the renderer to the REAL Python service over the two localhost WS channels
 * (impl-plan Task 5.9), feeding the SAME ingestion surface the mock fed — so the entire UI
 * is reused unchanged; only the source swaps. Frames → video sink + heartbeat; JSON → the
 * contact store + alert consideration + the mission log. Link state drives degrade-visibly. */

export function useRealService(config: { binaryUrl: string; jsonUrl: string } | null): void {
  useEffect(() => {
    if (!config) return;
    let frameId = 0;
    const seen = new Set<number>();

    const client = new RealWsClient(config, {
      onFrame: (jpeg) => {
        const id = frameId++;
        videoFrameSink.push({ frame_id: id, timestamp: id / 30, jpeg });
        useSystemStore.getState().markFrame(id); // heartbeat bound to real frame arrival
      },
      onJson: (m) => {
        useContactStore.getState().ingestJson(m);
        if (m.type === "contact") {
          useAlertStore.getState().consider(m);
          if (!seen.has(m.track_id)) {
            seen.add(m.track_id);
            useMissionLog.getState().append({
              kind: "detection",
              text: `trk ${m.track_id} NEW ${m.actionability_class}`,
              t: Date.now(),
            });
          }
        }
      },
      onLinkChange: (up) => {
        useSystemStore.getState().setLink(up);
        if (!up) {
          useMissionLog.getState().append({ kind: "link", text: "LINK LOST", t: Date.now() });
        }
      },
    });

    client.connect();
    // route the UI promote action → the WS promote command (the refined record returns via onJson)
    commandSink.setHandler((trackId) => {
      client.sendPromote(trackId);
      useMissionLog.getState().append({ kind: "note", text: `trk ${trackId} promote → fuse`, t: Date.now() });
    });
    return () => {
      commandSink.setHandler(null);
      client.close();
    };
  }, [config?.binaryUrl, config?.jsonUrl]);
}
