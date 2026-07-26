import type { ContactRecord, DetectionMessage } from "../types/wire";

/* MockWsServer — replays a canned mission over the SAME two-channel shape the real service
 * uses (impl-plan Task 5.1): a binary channel of JPEG frames and a JSON channel of
 * DetectionMessage / ContactRecord, aligned by frame_id. It exists so the whole UI (video
 * panel, map, list) runs deterministically + offline in Playwright with no Python service.
 * Selection/store wiring lives elsewhere; this is just the transport stand-in. */

/** One frame on the binary channel: JPEG bytes tagged with the join-key frame_id. */
export interface MockFrame {
  frame_id: number;
  timestamp: number;
  jpeg: Uint8Array;
}

type FrameListener = (f: MockFrame) => void;
type JsonListener = (m: DetectionMessage | ContactRecord) => void;
type Unsubscribe = () => void;

export interface MockWsConfig {
  frames: MockFrame[];
  json: (DetectionMessage | ContactRecord)[];
  /** Delay between emitted frames in ms; 0 = emit as fast as possible (tests). */
  intervalMs?: number;
}

export class MockWsServer {
  private readonly frames: MockFrame[];
  private readonly json: (DetectionMessage | ContactRecord)[];
  private readonly intervalMs: number;
  private readonly frameListeners = new Set<FrameListener>();
  private readonly jsonListeners = new Set<JsonListener>();
  private stopped = false;

  constructor(config: MockWsConfig) {
    this.frames = [...config.frames].sort((a, b) => a.frame_id - b.frame_id);
    this.json = config.json;
    this.intervalMs = config.intervalMs ?? 33; // ~30fps default
  }

  onFrame(cb: FrameListener): Unsubscribe {
    this.frameListeners.add(cb);
    return () => this.frameListeners.delete(cb);
  }

  onJson(cb: JsonListener): Unsubscribe {
    this.jsonListeners.add(cb);
    return () => this.jsonListeners.delete(cb);
  }

  /** Group JSON messages by the frame they belong to so both channels stay aligned. */
  private jsonByFrame(): Map<number, (DetectionMessage | ContactRecord)[]> {
    const byFrame = new Map<number, (DetectionMessage | ContactRecord)[]>();
    for (const m of this.json) {
      const list = byFrame.get(m.frame_id) ?? [];
      list.push(m);
      byFrame.set(m.frame_id, list);
    }
    return byFrame;
  }

  /** Replay the canned mission, frame by frame, emitting both channels in frame_id order. */
  async play(): Promise<void> {
    this.stopped = false;
    const byFrame = this.jsonByFrame();

    for (const frame of this.frames) {
      if (this.stopped) return;
      for (const cb of this.frameListeners) cb(frame);
      for (const m of byFrame.get(frame.frame_id) ?? []) {
        for (const cb of this.jsonListeners) cb(m);
      }
      if (this.intervalMs > 0) await delay(this.intervalMs);
    }
  }

  stop(): void {
    this.stopped = true;
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
