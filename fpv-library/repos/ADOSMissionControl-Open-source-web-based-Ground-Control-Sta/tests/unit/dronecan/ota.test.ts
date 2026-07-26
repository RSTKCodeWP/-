/**
 * @license GPL-3.0-only
 */

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { DroneCanClient } from "@/lib/dronecan/client";
import {
  DroneCanOtaOrchestrator,
  type OtaSnapshot,
} from "@/lib/dronecan/ota";
import { encodeTransfer } from "@/lib/dronecan/transfer-coder";
import { DATA_TYPE_IDS, DSDL_SIGNATURES } from "@/lib/dronecan/signatures";
import { DEFAULT_PRIORITY } from "@/lib/dronecan/frame-codec";
import {
  encodeBeginFirmwareUpdateResponse,
  ERROR_OK,
  ERROR_INVALID_MODE,
} from "@/lib/dronecan/dsdl/begin-firmware-update";
import { encodeGetNodeInfoResponse } from "@/lib/dronecan/dsdl/get-node-info";
import {
  encodeNodeStatus,
  MODE_OPERATIONAL,
  MODE_SOFTWARE_UPDATE,
  MODE_MAINTENANCE,
  HEALTH_OK,
} from "@/lib/dronecan/dsdl/node-status";
import {
  decodeFileReadResponse,
  encodeFileReadRequest,
} from "@/lib/dronecan/dsdl/file-read";
import type {
  CanFrame,
  CanTransport,
  CanTransportState,
  CanTransportStats,
} from "@/lib/protocol/transport/can-transport";

class MockTransport implements CanTransport {
  outbound: CanFrame[] = [];
  private frameListeners: Array<(f: CanFrame) => void> = [];
  private stateListeners: Array<(s: CanTransportState) => void> = [];

  async open(): Promise<void> {}
  async close(): Promise<void> {}
  async send(frame: CanFrame): Promise<void> {
    this.outbound.push(frame);
  }
  onFrame(cb: (frame: CanFrame) => void): () => void {
    this.frameListeners.push(cb);
    return () => {
      const i = this.frameListeners.indexOf(cb);
      if (i >= 0) this.frameListeners.splice(i, 1);
    };
  }
  onState(cb: (s: CanTransportState) => void): () => void {
    this.stateListeners.push(cb);
    return () => {
      const i = this.stateListeners.indexOf(cb);
      if (i >= 0) this.stateListeners.splice(i, 1);
    };
  }
  getState(): CanTransportState {
    return "open";
  }
  getStats(): CanTransportStats {
    return { txCount: 0, rxCount: 0, txErrors: 0, rxErrors: 0 };
  }

  inject(frame: CanFrame): void {
    for (const l of this.frameListeners) l(frame);
  }

  injectTransfer(args: {
    srcNodeId: number;
    dstNodeId?: number;
    dataTypeId: number;
    signature: bigint;
    transferId: number;
    kind: "message" | "response" | "request";
    payload: Uint8Array;
  }): void {
    const isService = args.kind !== "message";
    const frames = encodeTransfer(args.payload, {
      priority: DEFAULT_PRIORITY,
      dataTypeId: args.dataTypeId,
      srcNodeId: args.srcNodeId,
      dstNodeId: args.dstNodeId,
      isRequest: args.kind === "request",
      transferId: args.transferId,
      signature: args.signature,
      isService,
    });
    for (const f of frames) {
      this.inject({
        id: f.canId,
        extended: true,
        dlc: f.data.length,
        data: f.data,
      });
    }
  }
}

const SELF = 127;
const TARGET = 22;

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("DroneCanOtaOrchestrator — happy path", () => {
  it("walks ARMING → BEGIN_SENT → TRANSFERRING → REBOOTING → VERIFYING → DONE", async () => {
    const transport = new MockTransport();
    const client = new DroneCanClient(transport, { selfNodeId: SELF });
    await client.start();

    const snapshots: OtaSnapshot[] = [];
    const orchestrator = new DroneCanOtaOrchestrator(client);
    orchestrator.subscribe((s) => snapshots.push(s));

    const fileBytes = new Uint8Array(300);
    for (let i = 0; i < fileBytes.length; i++) fileBytes[i] = i & 0xff;

    const donePromise = orchestrator.start({
      targetNodeId: TARGET,
      fileBytes,
      expectedSwVersion: { major: 2, minor: 0 },
    });

    // First send: the BeginFirmwareUpdate request. Wait for it to flush.
    await Promise.resolve();
    await Promise.resolve();

    // Respond OK to BeginFirmwareUpdate.
    transport.injectTransfer({
      srcNodeId: TARGET,
      dstNodeId: SELF,
      dataTypeId: DATA_TYPE_IDS.fileBeginFirmwareUpdate,
      signature: DSDL_SIGNATURES.fileBeginFirmwareUpdate,
      transferId: 0,
      kind: "response",
      payload: encodeBeginFirmwareUpdateResponse({
        error: ERROR_OK,
        optional_error_message: "",
      }),
    });
    await Promise.resolve();
    await Promise.resolve();

    // Peripheral broadcasts NodeStatus MAINTENANCE first, then SOFTWARE_UPDATE.
    transport.injectTransfer({
      srcNodeId: TARGET,
      dataTypeId: DATA_TYPE_IDS.NodeStatus,
      signature: DSDL_SIGNATURES.NodeStatus,
      transferId: 0,
      kind: "message",
      payload: encodeNodeStatus({
        uptime_sec: 1,
        health: HEALTH_OK,
        mode: MODE_MAINTENANCE,
        vendor_specific_status_code: 0,
      }),
    });
    transport.injectTransfer({
      srcNodeId: TARGET,
      dataTypeId: DATA_TYPE_IDS.NodeStatus,
      signature: DSDL_SIGNATURES.NodeStatus,
      transferId: 1,
      kind: "message",
      payload: encodeNodeStatus({
        uptime_sec: 2,
        health: HEALTH_OK,
        mode: MODE_SOFTWARE_UPDATE,
        vendor_specific_status_code: 0,
      }),
    });
    await Promise.resolve();
    await Promise.resolve();

    // Walk through file.Read requests until EOF (300 bytes → two 256-byte
    // chunks and one empty terminator).
    await serveFileReadRequests(transport, fileBytes.length, TARGET, SELF);

    // Peripheral broadcasts OPERATIONAL → orchestrator runs verification.
    transport.injectTransfer({
      srcNodeId: TARGET,
      dataTypeId: DATA_TYPE_IDS.NodeStatus,
      signature: DSDL_SIGNATURES.NodeStatus,
      transferId: 5,
      kind: "message",
      payload: encodeNodeStatus({
        uptime_sec: 1,
        health: HEALTH_OK,
        mode: MODE_OPERATIONAL,
        vendor_specific_status_code: 0,
      }),
    });
    await Promise.resolve();
    await Promise.resolve();

    // Respond to GetNodeInfo with the matching version.
    transport.injectTransfer({
      srcNodeId: TARGET,
      dstNodeId: SELF,
      dataTypeId: DATA_TYPE_IDS.GetNodeInfo,
      signature: DSDL_SIGNATURES.GetNodeInfo,
      transferId: 0,
      kind: "response",
      payload: encodeGetNodeInfoResponse({
        status: {
          uptime_sec: 5,
          health: HEALTH_OK,
          mode: MODE_OPERATIONAL,
          vendor_specific_status_code: 0,
        },
        software_version: {
          major: 2,
          minor: 0,
          optional_field_flags: 0,
          vcs_commit: 0,
          image_crc: BigInt(0),
        },
        hardware_version: {
          major: 1,
          minor: 0,
          unique_id: new Uint8Array(16),
          certificate_of_authenticity: new Uint8Array(0),
        },
        name: "test-periph",
      }),
    });

    await donePromise;
    const last = snapshots[snapshots.length - 1];
    expect(last.state).toBe("DONE");
    expect(last.percent).toBe(100);
    expect(last.bytesTotal).toBe(300);
    // Ensure the state machine recorded the expected progression in the
    // transition log (snapshots may miss instantaneous states that emit no
    // snapshot of their own).
    const seenStates = new Set<string>();
    for (const entry of last.transitionLog) {
      seenStates.add(entry.from);
      seenStates.add(entry.to);
    }
    for (const expected of [
      "ARMING",
      "BEGIN_SENT",
      "TRANSFERRING",
      "REBOOTING",
      "VERIFYING",
      "DONE",
    ]) {
      expect(seenStates.has(expected)).toBe(true);
    }
    await client.stop();
  });
});

describe("DroneCanOtaOrchestrator — BEGIN_REJECTED failure", () => {
  it("transitions to FAILED with BEGIN_REJECTED when BeginFirmwareUpdate returns error", async () => {
    const transport = new MockTransport();
    const client = new DroneCanClient(transport, { selfNodeId: SELF });
    await client.start();

    const snapshots: OtaSnapshot[] = [];
    const orchestrator = new DroneCanOtaOrchestrator(client);
    orchestrator.subscribe((s) => snapshots.push(s));

    const promise = orchestrator.start({
      targetNodeId: TARGET,
      fileBytes: new Uint8Array(64),
    });

    await Promise.resolve();
    await Promise.resolve();
    transport.injectTransfer({
      srcNodeId: TARGET,
      dstNodeId: SELF,
      dataTypeId: DATA_TYPE_IDS.fileBeginFirmwareUpdate,
      signature: DSDL_SIGNATURES.fileBeginFirmwareUpdate,
      transferId: 0,
      kind: "response",
      payload: encodeBeginFirmwareUpdateResponse({
        error: ERROR_INVALID_MODE,
        optional_error_message: "node is armed",
      }),
    });

    await expect(promise).rejects.toThrow(/error=/);
    const last = snapshots[snapshots.length - 1];
    expect(last.state).toBe("FAILED");
    expect(last.errorCode).toBe("BEGIN_REJECTED");
    expect(last.beginError).toBe(ERROR_INVALID_MODE);
    await client.stop();
  });
});

// ── helpers ────────────────────────────────────────────────

/**
 * Drive the file-read request/response loop until the orchestrator has served
 * every chunk (including the empty EOF terminator).
 */
async function serveFileReadRequests(
  transport: MockTransport,
  fileSize: number,
  target: number,
  self: number,
): Promise<void> {
  let offset = 0;
  let transferId = 10;
  for (let i = 0; i < 8; i++) {
    transport.outbound.length = 0;
    transport.injectTransfer({
      srcNodeId: target,
      dstNodeId: self,
      dataTypeId: DATA_TYPE_IDS.fileRead,
      signature: DSDL_SIGNATURES.fileRead,
      transferId: transferId & 0x1f,
      kind: "request",
      payload: encodeFileReadRequest({
        offset: BigInt(offset),
        path: "a.bin",
      }),
    });
    transferId += 1;
    // Allow the async send to flush.
    await vi.advanceTimersByTimeAsync(1);
    await Promise.resolve();
    await Promise.resolve();
    if (transport.outbound.length === 0) break;
    const payload = reassemblePayload(transport.outbound);
    const res = decodeFileReadResponse(payload);
    offset += res.data.length;
    if (res.data.length === 0) break;
    if (offset >= fileSize) {
      // One more poll to drain the empty EOF response.
      transport.outbound.length = 0;
      transport.injectTransfer({
        srcNodeId: target,
        dstNodeId: self,
        dataTypeId: DATA_TYPE_IDS.fileRead,
        signature: DSDL_SIGNATURES.fileRead,
        transferId: transferId & 0x1f,
        kind: "request",
        payload: encodeFileReadRequest({
          offset: BigInt(offset),
          path: "a.bin",
        }),
      });
      await vi.advanceTimersByTimeAsync(1);
      await Promise.resolve();
      await Promise.resolve();
      break;
    }
  }
}

function reassemblePayload(frames: CanFrame[]): Uint8Array {
  if (frames.length === 0) return new Uint8Array(0);
  if (frames.length === 1) {
    return frames[0].data.subarray(0, frames[0].data.length - 1);
  }
  let total = 0;
  for (const f of frames) total += f.data.length - 1;
  const merged = new Uint8Array(total);
  let off = 0;
  for (const f of frames) {
    merged.set(f.data.subarray(0, f.data.length - 1), off);
    off += f.data.length - 1;
  }
  return merged.subarray(2);
}
