import { describe, expect, it } from "vitest";

import { FrameBuffer } from "./frameBuffer";
import type { MockFrame } from "../mock/mock-ws";

function f(frame_id: number): MockFrame {
  return { frame_id, timestamp: frame_id / 30, jpeg: new Uint8Array([0xff, 0xd8, frame_id]) };
}

/* Rolling frame buffer for the video panel (impl-plan Task 5.6): live playback shows the
 * latest frame (drop-to-latest), but the operator can PAUSE and REWIND through a bounded
 * history (instant scrub, no file I/O). The buffer is the model; the canvas renders
 * whatever frame the buffer says is "current". */

describe("FrameBuffer", () => {
  it("live mode tracks the latest pushed frame", () => {
    const b = new FrameBuffer(120);
    b.push(f(0));
    b.push(f(5));
    expect(b.current?.frame_id).toBe(5);
    expect(b.isLive).toBe(true);
  });

  it("caps history at its capacity (bounded memory)", () => {
    const b = new FrameBuffer(3);
    for (let i = 0; i < 10; i++) b.push(f(i));
    expect(b.size).toBe(3);
    expect(b.current?.frame_id).toBe(9);
  });

  it("pause freezes the current frame; new live frames don't advance the view", () => {
    const b = new FrameBuffer(120);
    b.push(f(10));
    b.pause();
    b.push(f(11));
    expect(b.isLive).toBe(false);
    expect(b.current?.frame_id).toBe(10); // stayed put while paused
  });

  it("rewind steps backward through buffered frames while paused", () => {
    const b = new FrameBuffer(120);
    for (let i = 0; i < 5; i++) b.push(f(i));
    b.pause();
    b.stepBack();
    b.stepBack();
    expect(b.current?.frame_id).toBe(2); // 4 → 3 → 2
  });

  it("cannot rewind past the oldest buffered frame", () => {
    const b = new FrameBuffer(120);
    b.push(f(0));
    b.push(f(1));
    b.pause();
    b.stepBack();
    b.stepBack();
    b.stepBack();
    expect(b.current?.frame_id).toBe(0);
  });

  it("resume snaps back to live (latest)", () => {
    const b = new FrameBuffer(120);
    for (let i = 0; i < 5; i++) b.push(f(i));
    b.pause();
    b.stepBack();
    b.push(f(5)); // arrived while paused
    b.resume();
    expect(b.isLive).toBe(true);
    expect(b.current?.frame_id).toBe(5);
  });
});
