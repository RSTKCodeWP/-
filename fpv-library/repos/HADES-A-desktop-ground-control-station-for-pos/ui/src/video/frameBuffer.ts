import type { MockFrame } from "../mock/mock-ws";

/* Rolling frame buffer for the video panel (impl-plan Task 5.6). Live: drop-to-latest, the
 * view follows the newest frame. Paused: the view is pinned to a cursor the operator scrubs
 * backward through a bounded history (instant rewind, no file I/O). Resume snaps to live.
 * Bounded capacity keeps memory flat over a long mission. */

export class FrameBuffer {
  private readonly frames: MockFrame[] = [];
  private live = true;
  private cursor = 0; // index into frames[] when paused

  constructor(private readonly capacity = 120) {}

  push(frame: MockFrame): void {
    this.frames.push(frame);
    if (this.frames.length > this.capacity) {
      this.frames.shift();
      if (!this.live && this.cursor > 0) this.cursor -= 1; // keep cursor on the same frame
    }
    if (this.live) this.cursor = this.frames.length - 1;
  }

  pause(): void {
    this.live = false;
  }

  resume(): void {
    this.live = true;
    this.cursor = this.frames.length - 1;
  }

  stepBack(): void {
    if (this.live) this.live = false;
    this.cursor = Math.max(0, this.cursor - 1);
  }

  stepForward(): void {
    this.cursor = Math.min(this.frames.length - 1, this.cursor + 1);
  }

  get current(): MockFrame | null {
    if (this.frames.length === 0) return null;
    const idx = this.live ? this.frames.length - 1 : this.cursor;
    return this.frames[idx] ?? null;
  }

  get isLive(): boolean {
    return this.live;
  }

  get size(): number {
    return this.frames.length;
  }
}
