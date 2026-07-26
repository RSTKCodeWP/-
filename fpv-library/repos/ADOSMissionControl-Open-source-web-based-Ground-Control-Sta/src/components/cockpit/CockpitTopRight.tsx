"use client";

/**
 * @module fly/cockpit/CockpitTopRight
 * @description The top-right cockpit cluster — a faithful port of the reference
 * artifact's `.zone.tr`: the density segmented control (Min / Std / Full), the
 * live video stats (resolution · fps · latency), and a camera pill.
 *
 * The camera pill names the node's primary (streaming) camera from the agent
 * capability probe — never a fabricated "main" label (Rule 44). When the node
 * advertises no camera roster the pill is omitted rather than inventing one;
 * when it advertises more than one, a `+N` hint points at the roster PiP. On a
 * multi-stream node the top-left stream switcher already names the active
 * stream, so the pill is omitted there to avoid a duplicate indicator.
 * @license GPL-3.0-only
 */

import { useVideoStore } from "@/stores/video-store";
import { useAgentCapabilitiesStore } from "@/stores/agent-capabilities-store";
import { useVideoStreamsStore } from "@/stores/video-streams-store";
import type { CockpitDensity } from "@/lib/cockpit/density";

const MODES: { id: CockpitDensity; label: string }[] = [
  { id: "minimal", label: "Min" },
  { id: "standard", label: "Std" },
  { id: "full", label: "Full" },
];

interface Props {
  density: CockpitDensity;
  onDensity: (d: CockpitDensity) => void;
  /** The cockpit's drone, so the pill can defer to the stream switcher on a
   * multi-stream node. Absent = never a multi-stream node (the pill shows). */
  droneId?: string;
}

export function CockpitTopRight({ density, onDensity, droneId }: Props) {
  const isStreaming = useVideoStore((s) => s.isStreaming);
  const fps = useVideoStore((s) => s.fps);
  const latencyMs = useVideoStore((s) => s.latencyMs);
  const resolution = useVideoStore((s) => s.resolution);
  const cameras = useAgentCapabilitiesStore((s) => s.cameras);
  const streamCount = useVideoStreamsStore((s) =>
    droneId ? (s.streamsByDrone[droneId]?.length ?? 0) : 0,
  );

  // The primary camera = the first streaming one, else the first advertised.
  // Never fabricate a "main" — with no roster the pill is simply absent. On a
  // multi-stream node the top-left switcher owns the active-stream indication,
  // so the pill is suppressed there to avoid duplicating it.
  const active =
    streamCount > 1
      ? null
      : (cameras.find((c) => c.streaming) ?? cameras[0] ?? null);
  const extra = cameras.length > 1 ? cameras.length - 1 : 0;

  return (
    <div className="zone tr">
      <div className="seg" role="group" aria-label="Information density">
        {MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            aria-pressed={density === m.id}
            onClick={() => onDensity(m.id)}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="vstats panel d-std">
        {isStreaming ? (
          <>
            <span className="s">
              <b>{resolution || "—"}</b>
            </span>
            <span className="s">
              <b>{Math.round(fps) || 0}</b>fps
            </span>
            <span className="s">
              <b>{Math.round(latencyMs) || 0}</b>ms
            </span>
          </>
        ) : (
          <span className="s">OFFLINE</span>
        )}
      </div>

      {active && (
        <div
          className={`camsel panel d-std${active.streaming ? "" : " idle"}`}
          data-camera-streaming={active.streaming}
        >
          <i className="dot" />
          <span title={active.name}>CAM · {active.name}</span>
          {extra > 0 && <span className="more">+{extra}</span>}
        </div>
      )}
    </div>
  );
}
