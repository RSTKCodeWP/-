/**
 * Web Worker hosting RTCRtpScriptTransform for SEI timestamp
 * extraction. Wired into the WHEP / WebRTC receive path before the
 * decoder so we can read the air-side capture timestamp embedded in
 * each H.264 frame.
 *
 * The transform NEVER modifies frames — every encoded frame is
 * enqueued back into the writable side untouched. The only side
 * effect is a postMessage carrying `{ rtpTimestamp, seiNs, recvMs }`
 * back to the main thread when an ADOS SEI is present.
 *
 * Wired up from `webrtc-client.ts` in the form:
 *
 *   const worker = new Worker(
 *     new URL("./sei-receiver-worker.ts", import.meta.url),
 *     { type: "module" },
 *   );
 *   receiver.transform = new RTCRtpScriptTransform(worker, { name: "ados-sei" });
 *
 * Bundlers (webpack, turbopack, vite) inline this file as a worker
 * chunk when they see the `new Worker(new URL(...), ...)` form.
 */

import { findAdosSeiTimestampNs } from "./sei-parser";

interface AdosSeiSample {
  // The RTP timestamp on the encoded frame, 90 kHz clock as published
  // by RTCEncodedVideoFrame.timestamp. Matches the timestamp the
  // <video> element's requestVideoFrameCallback metadata reports.
  rtpTimestamp: number;
  // Drone wall-clock timestamp at frame encode, in milliseconds.
  seiMs: number;
  // Browser monotonic clock at the moment we parsed the frame, in
  // milliseconds (performance.now() in the worker context).
  recvMs: number;
}

interface RtcTransformer {
  readable: ReadableStream<RTCEncodedVideoFrame>;
  writable: WritableStream<RTCEncodedVideoFrame>;
}

interface RtcTransformEvent extends Event {
  transformer: RtcTransformer;
}

// One-shot warn flag so a bad first frame doesn't spam the console.
let warnedOnce = false;

self.addEventListener("rtctransform", (event) => {
  const rtcEvent = event as RtcTransformEvent;
  const { readable, writable } = rtcEvent.transformer;

  readable
    .pipeThrough(
      new TransformStream<RTCEncodedVideoFrame, RTCEncodedVideoFrame>({
        transform(frame, controller) {
          try {
            const buf = new Uint8Array(frame.data);
            const seiNs = findAdosSeiTimestampNs(buf);
            if (seiNs !== null) {
              const sample: AdosSeiSample = {
                rtpTimestamp: (frame as unknown as { timestamp: number })
                  .timestamp,
                // Down-shift from BigInt nanoseconds to a regular ms
                // number for cheap postMessage transfer. We lose
                // sub-ms precision but gain JSON-cloneable types and
                // a ~292-million-year usable range from the epoch.
                seiMs: Number(seiNs / BigInt(1_000_000)),
                recvMs: performance.now(),
              };
              (self as unknown as Worker).postMessage(sample);
            }
          } catch (err) {
            if (!warnedOnce) {
              warnedOnce = true;
              console.warn(
                "[sei-receiver-worker] parse threw, continuing pass-through",
                err,
              );
            }
          }
          controller.enqueue(frame);
        },
      }),
    )
    .pipeTo(writable)
    .catch((err) => {
      // The pipe rejects when the receiver tears down; that's normal
      // on disconnect, not a worker bug.
      console.debug("[sei-receiver-worker] pipe closed", err);
    });
});

export {};
