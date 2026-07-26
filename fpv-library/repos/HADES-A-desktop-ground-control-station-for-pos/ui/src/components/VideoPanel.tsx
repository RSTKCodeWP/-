import { Camera, FlaskConical, Pause, Play, Plus, Rewind } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useContactStore } from "../store/contacts";
import { useProvenanceStore } from "../store/provenance";
import { useSystemStore } from "../store/system";
import { FrameBuffer } from "../video/frameBuffer";
import { overlayFreshness } from "../video/freshness";
import type { MockFrame } from "../mock/mock-ws";
import { STATUS_HEX } from "../map/layers";
import { latencyMeter } from "../perf/latency";

/* The video panel (impl-plan Task 5.6). Paints the binary-channel JPEG frame to a canvas
 * and draws detection boxes aligned by frame_id. Rolling buffer → instant rewind/pause.
 * Manual contact creation is the AI-miss backstop (recall-first). Loud LINK-LOST so a
 * frozen frame never looks live; fresh vs coasting overlays are visually distinct.
 *
 * Canvas painting is verified by screenshot; the controls, link state, and manual-contact
 * action are DOM-tested. The component reads the contact store for the latest detection. */

export function VideoPanel() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const bufferRef = useRef(new FrameBuffer(150));
  const [isLive, setIsLive] = useState(true);
  const [hasFrame, setHasFrame] = useState(false);

  const latestDetection = useContactStore((s) => s.latestDetection);
  const linkUp = useSystemStore((s) => s.linkUp);
  const addManualContact = useContactStore((s) => s.addManualContact);
  // Demo mode (provenance set) replays a near-black SYNTHETIC frame. Naming it keeps the panel
  // honest — a dark synthetic frame must never pose as a live feed (or read as a broken void).
  const isDemo = useProvenanceStore((s) => s.provenance !== null);

  // ingest frames pushed onto the buffer (wired to the mock/real WS in 5.1/5.9 via a ref API)
  useEffect(() => {
    const handler = (frame: MockFrame) => {
      latencyMeter.mark(frame.frame_id, "socket", performance.now()); // M3: frame on socket
      bufferRef.current.push(frame);
      setHasFrame(true);
      paint();
    };
    // expose a push hook on the window for the app/mock to feed frames (replaced by WS in 5.9)
    videoFrameSink.subscribe(handler);
    return () => videoFrameSink.unsubscribe(handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // repaint when the detection or link state changes
  useEffect(() => {
    paint();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [latestDetection, linkUp]);

  function paint() {
    const canvas = canvasRef.current;
    const frame = bufferRef.current.current;
    if (!canvas || !frame) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const draw = (img?: HTMLImageElement) => {
      ctx.fillStyle = "#06080C";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      if (img) ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      // box overlays aligned by frame_id — only draw boxes that belong to THIS frame
      const det = latestDetection;
      const fresh = overlayFreshness({
        linkUp,
        displayedFrameId: frame.frame_id,
        detectionFrameId: det?.frame_id ?? null,
      });
      if (det && det.frame_id === frame.frame_id) {
        const color = fresh === "FRESH" ? STATUS_HEX.warning : STATUS_HEX.stale;
        ctx.lineWidth = 2;
        ctx.strokeStyle = color;
        ctx.setLineDash(fresh === "COASTING" ? [4, 3] : []); // coasting = dashed
        for (const b of det.boxes) {
          const [x0, y0, x1, y1] = b.box_xyxy;
          ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
        }
        ctx.setLineDash([]);
      }
      // M3: frame painted with overlay → close the glass-to-glass sample for this frame
      latencyMeter.mark(frame.frame_id, "painted", performance.now());
      latencyMeter.commit(frame.frame_id);
    };

    // decode the JPEG bytes → image; fall back to a flat draw if decode fails
    try {
      const blob = new Blob([frame.jpeg as BlobPart], { type: "image/jpeg" });
      const url = URL.createObjectURL(blob);
      const img = new Image();
      img.onload = () => {
        latencyMeter.mark(frame.frame_id, "decoded", performance.now()); // M3: JPEG decoded
        draw(img);
        URL.revokeObjectURL(url);
      };
      img.onerror = () => {
        draw();
        URL.revokeObjectURL(url);
      };
      img.src = url;
    } catch {
      draw();
    }
  }

  const togglePause = () => {
    const b = bufferRef.current;
    if (b.isLive) b.pause();
    else b.resume();
    setIsLive(b.isLive);
    paint();
  };

  const rewind = () => {
    bufferRef.current.stepBack();
    setIsLive(bufferRef.current.isLive);
    paint();
  };

  return (
    <div className="relative flex h-full flex-col bg-video-letterbox">
      <div className="relative min-h-0 flex-1">
        <canvas
          ref={canvasRef}
          data-testid="video-canvas"
          width={960}
          height={540}
          className="h-full w-full object-contain"
        />
        {!hasFrame && (
          <div className="absolute inset-0 flex items-center justify-center font-mono text-2xs text-text-lo">
            No video — awaiting feed
          </div>
        )}
        {!linkUp && (
          <div
            data-testid="link-lost-banner"
            className="absolute inset-0 flex items-center justify-center bg-video-letterbox/70"
          >
            <span className="rounded-sm border border-st-critical px-3 py-1 font-mono text-sm font-bold text-st-critical">
              ⚠ LINK LOST · FROZEN
            </span>
          </div>
        )}
        {/* Demo mode: name the synthetic feed instead of the live FRESH indicator, so the
            near-black baked frame never poses as a live operational feed. Off-ramp violet-slate
            (--st-stale), matching the demo banner's "epistemic caveat, not an alarm" semantic. */}
        {isDemo ? (
          <span
            data-testid="video-demo-badge"
            className="absolute left-2 top-2 flex items-center gap-1.5 rounded-sm border border-st-stale/30 bg-video-letterbox/80 px-2 py-0.5 font-mono text-2xs text-st-stale"
          >
            <FlaskConical size={11} aria-hidden /> SYNTHETIC FEED · DEMO
          </span>
        ) : (
          hasFrame &&
          linkUp && (
            <span
              data-testid="fresh-indicator"
              className={`absolute left-2 top-2 rounded-sm bg-video-letterbox/80 px-2 py-0.5 font-mono text-2xs ${isLive ? "text-st-nominal" : "text-st-caution"}`}
            >
              {isLive ? "● FRESH" : "❚❚ PAUSED"}
            </span>
          )
        )}
      </div>

      {/* transport controls */}
      <div className="flex items-center gap-3 border-t border-hairline bg-surface-1 px-3 py-1 font-mono text-2xs text-text-mid">
        <button aria-label="rewind" onClick={rewind} className="flex items-center gap-1 hover:text-text-hi">
          <Rewind size={13} aria-hidden /> rewind
        </button>
        <button aria-label="pause" onClick={togglePause} className="flex items-center gap-1 hover:text-text-hi">
          {isLive ? <Pause size={13} aria-hidden /> : <Play size={13} aria-hidden />} {isLive ? "pause" : "play"}
        </button>
        <button aria-label="snapshot" className="flex items-center gap-1 hover:text-text-hi">
          <Camera size={13} aria-hidden /> snapshot
        </button>
        <button
          aria-label="manual contact"
          onClick={() => addManualContact()}
          className="ml-auto flex items-center gap-1 text-st-warning hover:brightness-110"
        >
          <Plus size={13} aria-hidden /> manual
        </button>
      </div>
    </div>
  );
}

/* A tiny pub-sub so the app/mock/real-WS can feed JPEG frames into the panel without
 * prop-drilling a stream through the layout. The mock wires onFrame → push here (Task 5.1);
 * the real preload bridge replaces the source in 5.9. */
type Sink = (f: MockFrame) => void;
class VideoFrameSink {
  private listeners = new Set<Sink>();
  subscribe(cb: Sink) {
    this.listeners.add(cb);
  }
  unsubscribe(cb: Sink) {
    this.listeners.delete(cb);
  }
  push(f: MockFrame) {
    for (const cb of this.listeners) cb(f);
  }
}
export const videoFrameSink = new VideoFrameSink();
