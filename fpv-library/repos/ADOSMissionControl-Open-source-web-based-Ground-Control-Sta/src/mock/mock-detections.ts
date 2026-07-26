/**
 * MockDetectionStream : a demo-mode synthetic vision-detection generator.
 *
 * Pushes realistic per-frame detection batches into the vision-detections
 * store at inference cadence (~10 Hz) so the cockpit's DetectionOverlay, the
 * video.overlay plugin slot, and the follow-me journey are fully explorable in
 * `npm run demo` with no agent attached. The store's setBatch is the same seam
 * the live LAN WebSocket client feeds, so the overlay code path is identical to
 * production.
 *
 * The stream produces 1-3 tracked "person" boxes that drift across the frame
 * (each on its own slow walk) with a stable trackId, and cycles each box's
 * lockState (locked -> uncertain -> locked) so the overlay's green/amber/red
 * colour ramp and the identity-uncertainty UI are exercised over time.
 *
 * This is demo infrastructure, not a stub: it is loaded only when isDemoMode()
 * is true and produces complete, well-formed data.
 *
 * @license GPL-3.0-only
 */

import {
  useVisionDetectionsStore,
  type LockState,
  type VisionDetection,
} from "@/stores/vision-detections-store";
import { useVideoStreamsStore } from "@/stores/video-streams-store";

/** Frame the synthetic boxes are expressed in (a common 4:3 inference size). */
const FRAME_WIDTH = 640;
const FRAME_HEIGHT = 480;

/** Push rate (ms) — ~10 Hz, matching a typical on-companion inference loop. */
const TICK_MS = 100;

/** One simulated track that drifts across the frame on a sinusoidal walk. */
interface MockTrack {
  trackId: number;
  classLabel: string;
  /** Box dimensions (px, frame space). */
  w: number;
  h: number;
  /** Walk parameters: base position, amplitude, angular speed, phase. */
  cx0: number;
  cy0: number;
  ax: number;
  ay: number;
  wx: number;
  wy: number;
  phase: number;
  /** Seconds spent on the locked/uncertain lock-state cycle offset. */
  lockPhase: number;
}

/** The fixed cast of tracks. The generator shows a count that breathes 1..3. */
const TRACKS: MockTrack[] = [
  {
    trackId: 7,
    classLabel: "person",
    w: 90,
    h: 190,
    cx0: 200,
    cy0: 250,
    ax: 110,
    ay: 40,
    wx: 0.18,
    wy: 0.32,
    phase: 0,
    lockPhase: 0,
  },
  {
    trackId: 12,
    classLabel: "person",
    w: 80,
    h: 170,
    cx0: 430,
    cy0: 240,
    ax: 90,
    ay: 60,
    wx: 0.24,
    wy: 0.2,
    phase: 1.7,
    lockPhase: 2.1,
  },
  {
    trackId: 21,
    classLabel: "person",
    w: 70,
    h: 150,
    cx0: 320,
    cy0: 300,
    ax: 130,
    ay: 30,
    wx: 0.14,
    wy: 0.27,
    phase: 3.4,
    lockPhase: 4.3,
  },
];

/** Cycle a lock state on a slow period so the overlay colour ramp animates. */
function lockStateAt(tSec: number, offset: number): LockState {
  // ~7s period: ~5s locked, ~1.5s uncertain, brief lost, back to locked.
  const p = (tSec + offset) % 7;
  if (p < 5) return "locked";
  if (p < 6.5) return "uncertain";
  return "lost";
}

class MockDetectionStream {
  private intervalId: ReturnType<typeof setInterval> | null = null;
  private droneId: string | null = null;
  private startMs = 0;
  private frameId = 0;

  /** Start (or retarget) the stream onto a drone id. Idempotent per drone. */
  start(droneId: string): void {
    if (this.intervalId !== null && this.droneId === droneId) return;
    this.stop();
    this.droneId = droneId;
    this.startMs = Date.now();
    this.frameId = 0;
    this.intervalId = setInterval(() => this.tick(), TICK_MS);
  }

  stop(): void {
    if (this.intervalId !== null) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    if (this.droneId) {
      useVisionDetectionsStore.getState().clearBatch(this.droneId);
    }
    this.droneId = null;
  }

  isRunning(): boolean {
    return this.intervalId !== null;
  }

  private tick(): void {
    const droneId = this.droneId;
    if (!droneId) return;

    const tSec = (Date.now() - this.startMs) / 1000;
    // Breathe the visible count 1 -> 2 -> 3 -> 2 -> 1 on a slow cycle so the
    // overlay sees tracks appear and disappear.
    const visible = 1 + Math.round(1 + Math.sin(tSec * 0.25)); // 1..3

    const detections: VisionDetection[] = [];
    for (let i = 0; i < Math.min(visible, TRACKS.length); i++) {
      const tr = TRACKS[i];
      const cx = tr.cx0 + tr.ax * Math.sin(tSec * tr.wx + tr.phase);
      const cy = tr.cy0 + tr.ay * Math.sin(tSec * tr.wy + tr.phase * 1.3);
      const x = clamp(cx - tr.w / 2, 0, FRAME_WIDTH - tr.w);
      const y = clamp(cy - tr.h / 2, 0, FRAME_HEIGHT - tr.h);
      const lockState = lockStateAt(tSec, tr.lockPhase);
      // Confidence + association dip while uncertain/lost, matching the lock.
      const conf =
        lockState === "locked"
          ? 0.9
          : lockState === "uncertain"
            ? 0.62
            : 0.38;
      detections.push({
        bbox: { x, y, width: tr.w, height: tr.h },
        classLabel: tr.classLabel,
        confidence: conf,
        trackId: tr.trackId,
        assocConfidence: conf,
        lockState,
      });
    }

    // Tag the batch with the currently-active video leg so the demo models a
    // single-tracker pod that follows the active camera: the cockpit overlay
    // correlates boxes to the active leg id, so the boxes stay on the main view
    // as the operator switches legs (and never bleed onto another leg).
    const cameraId =
      useVideoStreamsStore.getState().activeStream(droneId)?.id ?? "demo-cam-0";
    useVisionDetectionsStore.getState().setBatch(droneId, {
      modelId: "demo-yolov8n",
      cameraId,
      frameId: this.frameId++,
      tsMs: Date.now(),
      frameWidth: FRAME_WIDTH,
      frameHeight: FRAME_HEIGHT,
      detections,
    });
  }
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/** Singleton demo detection stream. */
export const mockDetectionStream = new MockDetectionStream();
