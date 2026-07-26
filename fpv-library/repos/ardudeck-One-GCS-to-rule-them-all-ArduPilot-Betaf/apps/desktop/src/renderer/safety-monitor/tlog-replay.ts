/**
 * .tlog replay for the Safety Monitor.
 *
 * A .tlog is a sequence of records, each an 8-byte big-endian microsecond
 * timestamp followed by one raw MAVLink frame - byte-identical to the live
 * wire. We parse it client-side (pure JS, no node:crypto) and feed the frames
 * through the SAME decode path the live link uses (source.feedReplayPacket),
 * so replay needs no special-cased units or logic. This is what makes the
 * acceptance test ("escalate to DANGER on a known tip-over log before attitude
 * blows past 30deg") run against real recorded data.
 */

import {
  beginReplay,
  endReplay,
  feedReplayPacket,
  evaluateReplayAt,
} from './source';

export interface ReplayPacket {
  /** Log time in milliseconds. */
  t: number;
  msgid: number;
  sysid: number;
  compid: number;
  payload: number[];
}

const MAGIC_V1 = 0xfe;
const MAGIC_V2 = 0xfd;
const MAVLINK_IFLAG_SIGNED = 0x01;

/** Parse a .tlog buffer into time-ordered raw packets. */
export function parseTlog(buffer: ArrayBuffer): ReplayPacket[] {
  const buf = new Uint8Array(buffer);
  const view = new DataView(buffer);
  const out: ReplayPacket[] = [];
  let pos = 0;

  while (pos + 8 < buf.length) {
    const tUs = view.getBigUint64(pos, false); // big-endian microseconds
    const t = Number(tUs / 1000n);
    const magicPos = pos + 8;
    const magic = buf[magicPos];

    if (magic === MAGIC_V2) {
      if (magicPos + 10 > buf.length) break;
      const payloadLen = buf[magicPos + 1]!;
      const incompat = buf[magicPos + 2]!;
      const sysid = buf[magicPos + 5]!;
      const compid = buf[magicPos + 6]!;
      const msgid = buf[magicPos + 7]! | (buf[magicPos + 8]! << 8) | (buf[magicPos + 9]! << 16);
      const payloadStart = magicPos + 10;
      const payload = Array.from(buf.slice(payloadStart, payloadStart + payloadLen));
      const sigLen = (incompat & MAVLINK_IFLAG_SIGNED) !== 0 ? 13 : 0;
      const frameLen = 10 + payloadLen + 2 + sigLen;
      out.push({ t, msgid, sysid, compid, payload });
      pos = magicPos + frameLen;
    } else if (magic === MAGIC_V1) {
      if (magicPos + 6 > buf.length) break;
      const payloadLen = buf[magicPos + 1]!;
      const sysid = buf[magicPos + 3]!;
      const compid = buf[magicPos + 4]!;
      const msgid = buf[magicPos + 5]!;
      const payloadStart = magicPos + 6;
      const payload = Array.from(buf.slice(payloadStart, payloadStart + payloadLen));
      const frameLen = 6 + payloadLen + 2;
      out.push({ t, msgid, sysid, compid, payload });
      pos = magicPos + frameLen;
    } else {
      // Not a frame boundary - resync by scanning forward one byte at a time.
      pos += 1;
    }
  }

  return out;
}

export interface ReplayHandle {
  stop: () => void;
}

export interface ReplayOptions {
  /** Playback speed multiplier over log time (default 20x). */
  speed?: number;
  /** Engine evaluation cadence in log-time ms (default 100 = 10 Hz). */
  evalStepMs?: number;
  onProgress?: (fraction: number) => void;
  onDone?: () => void;
}

/**
 * Play parsed packets through the engine. Packets are delivered in log order;
 * the engine is evaluated every evalStepMs of log time. Wall-clock pacing is
 * compressed by `speed` so a 5-minute log can be reviewed in seconds.
 */
export function runReplay(packets: ReplayPacket[], opts: ReplayOptions = {}): ReplayHandle {
  const speed = opts.speed ?? 20;
  const evalStepMs = opts.evalStepMs ?? 100;
  if (packets.length === 0) {
    opts.onDone?.();
    return { stop: () => {} };
  }

  beginReplay();
  const t0 = packets[0]!.t;
  const tEnd = packets[packets.length - 1]!.t;
  let idx = 0;
  let logCursor = t0;

  // Each wall-clock tick advances log time by (tickMs * speed).
  const tickMs = 50;
  const handle = setInterval(() => {
    const advance = tickMs * speed;
    const target = logCursor + advance;

    // Feed every packet up to the new cursor.
    while (idx < packets.length && packets[idx]!.t <= target) {
      const p = packets[idx]!;
      feedReplayPacket({ msgid: p.msgid, sysid: p.sysid, compid: p.compid, payload: p.payload }, p.t);
      idx += 1;
    }

    // Evaluate the engine in evalStepMs increments across the span just
    // covered so debounce timing matches the real timeline.
    for (let e = logCursor + evalStepMs; e <= target; e += evalStepMs) {
      evaluateReplayAt(e);
    }
    logCursor = target;

    opts.onProgress?.(Math.min(1, (logCursor - t0) / Math.max(1, tEnd - t0)));

    if (idx >= packets.length && logCursor >= tEnd) {
      clearInterval(handle);
      endReplay();
      opts.onDone?.();
    }
  }, tickMs);

  return {
    stop: () => {
      clearInterval(handle);
      endReplay();
    },
  };
}
