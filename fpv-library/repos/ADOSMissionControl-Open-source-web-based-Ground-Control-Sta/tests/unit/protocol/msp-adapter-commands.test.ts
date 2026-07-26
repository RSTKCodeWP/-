/**
 * MSP command-translation layer tests.
 *
 * The MSP codec (frame encode/decode) and the serial queue are covered
 * elsewhere. This file pins the layer between them: the functions that
 * turn a high-level command (arm, disarm, motor test, kill switch, reboot,
 * calibrate) into a concrete MSP command id plus payload bytes. A wrong
 * AUX-channel index, a wrong throttle byte, or a swapped command id is a
 * real-flight hazard, so each case asserts the exact id and the exact
 * bytes, then round-trips the captured frame through the real codec +
 * parser to prove the bytes survive the wire.
 */
import { describe, it, expect } from 'vitest';
import {
  mspArm,
  mspDisarm,
  mspSetFlightMode,
  mspMotorTest,
  mspKillSwitch,
  mspReboot,
  mspRebootToBootloader,
  mspStartCalibration,
  mspCommitParamsToFlash,
  mspSendManualControl,
  type MspCommandContext,
} from '@/lib/protocol/msp-adapter-commands';
import type { MspSerialQueue } from '@/lib/protocol/msp/msp-serial-queue';
import { MSP } from '@/lib/protocol/msp/msp-constants';
import type { ModeRange } from '@/lib/protocol/msp/msp-mode-map';
import { encodeMsp } from '@/lib/protocol/msp/msp-codec';
import { MspParser } from '@/lib/protocol/msp/msp-parser';

// ── Capturing fake queue ───────────────────────────────────

interface CapturedFrame {
  command: number;
  payload: Uint8Array;
  awaited: boolean; // true for send(), false for sendNoReply()
}

/**
 * Records every command + payload the translation layer emits without
 * touching a transport. send() resolves with an empty response frame so
 * the caller's success branch runs (none of the tested commands read the
 * response payload).
 */
function createCapturingQueue() {
  const frames: CapturedFrame[] = [];
  const queue = {
    send(command: number, payload?: Uint8Array) {
      frames.push({ command, payload: payload ?? new Uint8Array(0), awaited: true });
      return Promise.resolve({
        version: 1 as const,
        command,
        payload: new Uint8Array(0),
        direction: 'response' as const,
      });
    },
    sendNoReply(command: number, payload?: Uint8Array) {
      frames.push({ command, payload: payload ?? new Uint8Array(0), awaited: false });
    },
  };
  return { queue: queue as unknown as MspSerialQueue, frames };
}

/** Read a little-endian 16-bit value from a payload at byte offset. */
function readU16(buf: Uint8Array, offset: number): number {
  return buf[offset] | (buf[offset + 1] << 8);
}

/**
 * Re-encode a captured frame, feed it through the real streaming parser,
 * and return the decoded command + payload. Proves the captured bytes
 * survive a codec round-trip unchanged.
 */
function roundTrip(frame: CapturedFrame): { command: number; payload: Uint8Array } {
  const parser = new MspParser();
  let decoded: { command: number; payload: Uint8Array } | null = null;
  parser.onFrame((f) => {
    decoded = { command: f.command, payload: f.payload };
  });
  // The codec emits a request ($M< / $X<); the parser accepts the
  // direction byte regardless, so we route the encoded request back in.
  parser.feed(encodeMsp(frame.command, frame.payload));
  if (!decoded) throw new Error(`frame for command ${frame.command} failed to round-trip`);
  return decoded;
}

const ARM_RANGE: ModeRange = {
  boxId: 0, // ARM
  auxChannel: 1, // AUX2
  rangeStart: 1700,
  rangeEnd: 2100,
};

function ctxWith(ranges: ModeRange[]): { ctx: MspCommandContext; frames: CapturedFrame[] } {
  const { queue, frames } = createCapturingQueue();
  return { ctx: { queue, modeRanges: ranges }, frames };
}

// ── Arm / Disarm without an arm mode range ─────────────────

describe('mspArm / mspDisarm with no arm ModeRange', () => {
  it('arm sends MSP_ARMING_DISABLE with payload[0]===0 (enable arming)', async () => {
    const { ctx, frames } = ctxWith([]);
    const result = await mspArm(ctx);
    expect(result.success).toBe(true);
    expect(frames).toHaveLength(1);
    expect(frames[0].command).toBe(MSP.MSP_ARMING_DISABLE);
    expect(frames[0].awaited).toBe(true);
    expect(frames[0].payload[0]).toBe(0);

    const rt = roundTrip(frames[0]);
    expect(rt.command).toBe(MSP.MSP_ARMING_DISABLE);
    expect(rt.payload[0]).toBe(0);
  });

  it('disarm sends MSP_ARMING_DISABLE with payload[0]===1 (disable arming)', async () => {
    const { ctx, frames } = ctxWith([]);
    const result = await mspDisarm(ctx);
    expect(result.success).toBe(true);
    expect(frames).toHaveLength(1);
    expect(frames[0].command).toBe(MSP.MSP_ARMING_DISABLE);
    expect(frames[0].payload[0]).toBe(1);

    const rt = roundTrip(frames[0]);
    expect(rt.payload[0]).toBe(1);
  });
});

// ── Arm / Disarm WITH an arm mode range (AUX path) ─────────

describe('mspArm / mspDisarm with an arm ModeRange (AUX channel path)', () => {
  it('arm writes MSP_SET_RAW_RC putting AUX(auxChannel) at the range midpoint', async () => {
    const { ctx, frames } = ctxWith([ARM_RANGE]);
    const result = await mspArm(ctx);
    expect(result.success).toBe(true);
    expect(frames).toHaveLength(1);

    const frame = frames[0];
    expect(frame.command).toBe(MSP.MSP_SET_RAW_RC);
    expect(frame.awaited).toBe(false); // fire-and-forget RC
    // 8 channels * 2 bytes
    expect(frame.payload).toHaveLength(16);

    // The arm range is auxChannel=1, so the activated RC channel is
    // index auxChannel + 4 = 5 (the first four channels are roll/pitch/
    // throttle/yaw). The PWM is the midpoint of [1700, 2100] = 1900.
    const channelIndex = ARM_RANGE.auxChannel + 4;
    const mid = Math.round((ARM_RANGE.rangeStart + ARM_RANGE.rangeEnd) / 2);
    expect(mid).toBe(1900);
    expect(readU16(frame.payload, channelIndex * 2)).toBe(1900);

    // Throttle (channel index 2) is held at the disarmed-safe 1000.
    expect(readU16(frame.payload, 2 * 2)).toBe(1000);
    // Roll / pitch / yaw centered.
    expect(readU16(frame.payload, 0)).toBe(1500);
    expect(readU16(frame.payload, 1 * 2)).toBe(1500);
    expect(readU16(frame.payload, 3 * 2)).toBe(1500);

    const rt = roundTrip(frame);
    expect(rt.command).toBe(MSP.MSP_SET_RAW_RC);
    expect(readU16(rt.payload, channelIndex * 2)).toBe(1900);
  });

  it('disarm writes MSP_SET_RAW_RC putting the same AUX channel low (1000)', async () => {
    const { ctx, frames } = ctxWith([ARM_RANGE]);
    const result = await mspDisarm(ctx);
    expect(result.success).toBe(true);

    const frame = frames[0];
    expect(frame.command).toBe(MSP.MSP_SET_RAW_RC);
    const channelIndex = ARM_RANGE.auxChannel + 4;
    expect(readU16(frame.payload, channelIndex * 2)).toBe(1000);
  });
});

// ── Motor test ─────────────────────────────────────────────

describe('mspMotorTest', () => {
  it('sends MSP_SET_MOTOR scaling only the selected motor, others at 1000', async () => {
    const { ctx, frames } = ctxWith([]);
    const result = await mspMotorTest(ctx, 2, 50);
    expect(result.success).toBe(true);
    expect(frames).toHaveLength(1);

    const frame = frames[0];
    expect(frame.command).toBe(MSP.MSP_SET_MOTOR);
    expect(frame.awaited).toBe(true);
    expect(frame.payload).toHaveLength(16); // 8 motors * 2 bytes

    // Motor index 2 at 50% => 1000 + (50/100)*1000 = 1500.
    expect(readU16(frame.payload, 2 * 2)).toBe(1500);
    // Every other motor sits at the stop value 1000.
    for (let i = 0; i < 8; i++) {
      if (i === 2) continue;
      expect(readU16(frame.payload, i * 2)).toBe(1000);
    }

    const rt = roundTrip(frame);
    expect(rt.command).toBe(MSP.MSP_SET_MOTOR);
    expect(readU16(rt.payload, 2 * 2)).toBe(1500);
  });

  it('100% throttle on motor 0 maps to the full 2000 PWM', async () => {
    const { ctx, frames } = ctxWith([]);
    await mspMotorTest(ctx, 0, 100);
    expect(readU16(frames[0].payload, 0)).toBe(2000);
  });

  it('0% throttle leaves the selected motor at the 1000 stop value', async () => {
    const { ctx, frames } = ctxWith([]);
    await mspMotorTest(ctx, 5, 0);
    expect(readU16(frames[0].payload, 5 * 2)).toBe(1000);
  });
});

// ── Kill switch ────────────────────────────────────────────

describe('mspKillSwitch', () => {
  it('sends MSP_SET_RAW_RC dropping throttle to the 885 cut value', async () => {
    const { ctx, frames } = ctxWith([]);
    const result = await mspKillSwitch(ctx);
    expect(result.success).toBe(true);
    expect(frames).toHaveLength(1);

    const frame = frames[0];
    expect(frame.command).toBe(MSP.MSP_SET_RAW_RC);
    expect(frame.awaited).toBe(false); // fire-and-forget, no ACK wait
    expect(frame.payload).toHaveLength(16);

    // Channel 2 is throttle; the kill drops it below the arm threshold.
    expect(readU16(frame.payload, 2 * 2)).toBe(885);
    // Roll / pitch / yaw stay centered.
    expect(readU16(frame.payload, 0)).toBe(1500);
    expect(readU16(frame.payload, 1 * 2)).toBe(1500);
    expect(readU16(frame.payload, 3 * 2)).toBe(1500);
    // AUX channels low.
    for (let i = 4; i < 8; i++) {
      expect(readU16(frame.payload, i * 2)).toBe(1000);
    }

    const rt = roundTrip(frame);
    expect(readU16(rt.payload, 2 * 2)).toBe(885);
  });
});

// ── Reboot / bootloader ────────────────────────────────────

describe('mspReboot / mspRebootToBootloader', () => {
  it('reboot sends MSP_SET_REBOOT with payload[0]===0 (normal reboot)', async () => {
    const { ctx, frames } = ctxWith([]);
    const result = await mspReboot(ctx);
    expect(result.success).toBe(true);
    expect(frames[0].command).toBe(MSP.MSP_SET_REBOOT);
    expect(frames[0].payload[0]).toBe(0);

    const rt = roundTrip(frames[0]);
    expect(rt.command).toBe(MSP.MSP_SET_REBOOT);
    expect(rt.payload[0]).toBe(0);
  });

  it('bootloader reboot sends MSP_SET_REBOOT with payload[0]===1', async () => {
    const { ctx, frames } = ctxWith([]);
    const result = await mspRebootToBootloader(ctx);
    expect(result.success).toBe(true);
    expect(frames[0].command).toBe(MSP.MSP_SET_REBOOT);
    expect(frames[0].payload[0]).toBe(1);
  });
});

// ── Calibration ────────────────────────────────────────────

describe('mspStartCalibration', () => {
  it('accel calibration sends MSP_ACC_CALIBRATION with no payload', async () => {
    const { ctx, frames } = ctxWith([]);
    const result = await mspStartCalibration(ctx, 'accel');
    expect(result.success).toBe(true);
    expect(frames[0].command).toBe(MSP.MSP_ACC_CALIBRATION);
    expect(frames[0].payload).toHaveLength(0);
  });

  it('level calibration also maps to MSP_ACC_CALIBRATION', async () => {
    const { ctx, frames } = ctxWith([]);
    const result = await mspStartCalibration(ctx, 'level');
    expect(result.success).toBe(true);
    expect(frames[0].command).toBe(MSP.MSP_ACC_CALIBRATION);
  });

  it('compass calibration sends MSP_MAG_CALIBRATION', async () => {
    const { ctx, frames } = ctxWith([]);
    const result = await mspStartCalibration(ctx, 'compass');
    expect(result.success).toBe(true);
    expect(frames[0].command).toBe(MSP.MSP_MAG_CALIBRATION);
  });

  it('an unsupported calibration type fails and sends nothing', async () => {
    const { ctx, frames } = ctxWith([]);
    const result = await mspStartCalibration(ctx, 'esc');
    expect(result.success).toBe(false);
    expect(result.message).toContain('esc');
    expect(frames).toHaveLength(0);
  });
});

// ── EEPROM commit ──────────────────────────────────────────

describe('mspCommitParamsToFlash', () => {
  it('sends MSP_EEPROM_WRITE', async () => {
    const { ctx, frames } = ctxWith([]);
    const result = await mspCommitParamsToFlash(ctx);
    expect(result.success).toBe(true);
    expect(frames[0].command).toBe(MSP.MSP_EEPROM_WRITE);
  });
});

// ── Manual control (RC override stream) ────────────────────

describe('mspSendManualControl', () => {
  it('maps -1000..1000 stick axes to 1000..2000 PWM via MSP_SET_RAW_RC', () => {
    const { ctx, frames } = ctxWith([]);
    mspSendManualControl(ctx, 1000, -1000, 0, 500);
    expect(frames).toHaveLength(1);

    const frame = frames[0];
    expect(frame.command).toBe(MSP.MSP_SET_RAW_RC);
    expect(frame.awaited).toBe(false);
    expect(frame.payload).toHaveLength(16);

    // value / 2 + 1500: roll 1000 -> 2000, pitch -1000 -> 1000,
    // throttle 0 -> 1500, yaw 500 -> 1750.
    expect(readU16(frame.payload, 0)).toBe(2000);
    expect(readU16(frame.payload, 1 * 2)).toBe(1000);
    expect(readU16(frame.payload, 2 * 2)).toBe(1500);
    expect(readU16(frame.payload, 3 * 2)).toBe(1750);
    // The four AUX channels hold center.
    for (let i = 4; i < 8; i++) {
      expect(readU16(frame.payload, i * 2)).toBe(1500);
    }
  });
});

// ── Flight-mode switch is intentionally unsupported ────────

describe('mspSetFlightMode', () => {
  it('returns a not-supported result and never touches the queue (no bit mapping)', async () => {
    const { ctx, frames } = ctxWith([]);
    const result = await mspSetFlightMode(ctx, 'STABILIZE');
    expect(result.success).toBe(false);
    expect(result.resultCode).toBe(-1);
    expect(frames).toHaveLength(0);
  });
});

// ── Disconnected guard ─────────────────────────────────────

describe('not-connected guard', () => {
  it('every command returns "Not connected" when the queue is null and sends nothing', async () => {
    const ctx: MspCommandContext = { queue: null, modeRanges: [] };
    for (const result of [
      await mspArm(ctx),
      await mspDisarm(ctx),
      await mspMotorTest(ctx, 0, 50),
      await mspKillSwitch(ctx),
      await mspReboot(ctx),
      await mspRebootToBootloader(ctx),
      await mspStartCalibration(ctx, 'accel'),
      await mspCommitParamsToFlash(ctx),
    ]) {
      expect(result.success).toBe(false);
      expect(result.message).toBe('Not connected');
    }
  });
});
