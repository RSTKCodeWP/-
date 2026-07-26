/**
 * @module protocol/firmware/dronecan-ota
 * @description `FirmwareFlasher` adapter for the DroneCAN OTA orchestrator.
 * Wires `OtaSnapshot` updates into the `FlashProgress` callback shape so the
 * existing Flash Tool UI can show a CAN-side flash as just another method.
 *
 * Verification is folded into the orchestrator's own VERIFYING step during
 * `flash()` (it calls `GetNodeInfo` and compares the reported software version).
 *
 * @license GPL-3.0-only
 */

import type {
  FirmwareFlasher,
  FlashMethod,
  FlashPhase,
  FlashProgress,
  FlashProgressCallback,
  ParsedFirmware,
} from "./types";
import type { DroneCanClient } from "../../dronecan/client";
import {
  DroneCanOtaOrchestrator,
  type OtaSnapshot,
  type OtaState,
} from "../../dronecan/ota";

/** Constructor options for the OTA flasher. */
export interface DroneCanOtaFlasherOptions {
  /** Live DroneCAN client. The caller owns its lifecycle. */
  client: DroneCanClient;
  /** Node ID of the peripheral to flash. */
  targetNodeId: number;
  /** Node ID announced inside BeginFirmwareUpdate. Defaults to client self. */
  sourceNodeId?: number;
  /** Optional expected software version (logged on mismatch). */
  expectedSwVersion?: { major: number; minor: number };
}

const STATE_TO_PHASE: Record<OtaState, FlashPhase> = {
  IDLE: "idle",
  ARMING: "backup",
  BEGIN_SENT: "bootloader_wait",
  TRANSFERRING: "flashing",
  REBOOTING: "restarting",
  VERIFYING: "verifying",
  DONE: "done",
  ABORTED: "error",
  FAILED: "error",
};

/** Pretty message for the active state. */
function stateMessage(snap: OtaSnapshot): string {
  switch (snap.state) {
    case "ARMING":
      return "Preparing firmware upload";
    case "BEGIN_SENT":
      return "Waiting for peripheral to enter software-update mode";
    case "TRANSFERRING":
      return `Streaming firmware: ${snap.bytesSent} / ${snap.bytesTotal} bytes`;
    case "REBOOTING":
      return "Peripheral is rebooting";
    case "VERIFYING":
      return "Verifying peripheral firmware version";
    case "DONE":
      return "Firmware update complete";
    case "ABORTED":
      return "Firmware update aborted";
    case "FAILED":
      return snap.errorMessage ?? "Firmware update failed";
    default:
      return "Idle";
  }
}

/**
 * `FirmwareFlasher` implementation that drives the DroneCAN OTA flow against a
 * peripheral node sitting on the bus.
 */
export class DroneCanOtaFlasher implements FirmwareFlasher {
  readonly method: FlashMethod = "dronecan-ota";
  private readonly opts: DroneCanOtaFlasherOptions;
  private orchestrator: DroneCanOtaOrchestrator | null = null;
  private unsubscribe: (() => void) | null = null;
  private disposed = false;

  constructor(opts: DroneCanOtaFlasherOptions) {
    this.opts = opts;
  }

  /** Drive the full OTA flow. Resolves when the peripheral reports DONE. */
  async flash(
    firmware: ParsedFirmware,
    onProgress: FlashProgressCallback,
    signal?: AbortSignal,
  ): Promise<void> {
    if (this.disposed) {
      throw new Error("DroneCanOtaFlasher has been disposed");
    }
    if (firmware.blocks.length === 0) {
      throw new Error("firmware has no blocks");
    }
    const fileBytes = flattenBlocks(firmware);

    this.orchestrator = new DroneCanOtaOrchestrator(this.opts.client);
    this.unsubscribe = this.orchestrator.subscribe((snap) => {
      onProgress(mapSnapshot(snap));
    });

    if (signal) {
      if (signal.aborted) {
        this.orchestrator.abort();
        throw new Error("Flash aborted by user");
      }
      const onAbort = () => this.orchestrator?.abort();
      signal.addEventListener("abort", onAbort, { once: true });
      try {
        await this.orchestrator.start({
          targetNodeId: this.opts.targetNodeId,
          fileBytes,
          sourceNodeId: this.opts.sourceNodeId,
          expectedSwVersion: this.opts.expectedSwVersion,
        });
      } finally {
        signal.removeEventListener("abort", onAbort);
      }
      return;
    }

    await this.orchestrator.start({
      targetNodeId: this.opts.targetNodeId,
      fileBytes,
      sourceNodeId: this.opts.sourceNodeId,
      expectedSwVersion: this.opts.expectedSwVersion,
    });
  }

  /** Abort an in-flight OTA. */
  abort(): void {
    this.orchestrator?.abort();
  }

  /** Detach subscribers and release resources. Idempotent. */
  async dispose(): Promise<void> {
    if (this.disposed) return;
    this.disposed = true;
    this.unsubscribe?.();
    this.unsubscribe = null;
    this.orchestrator = null;
  }
}

function flattenBlocks(firmware: ParsedFirmware): Uint8Array {
  if (firmware.blocks.length === 1) {
    return firmware.blocks[0].data;
  }
  const out = new Uint8Array(firmware.totalBytes);
  let off = 0;
  for (const b of firmware.blocks) {
    out.set(b.data, off);
    off += b.data.length;
  }
  return out;
}

function mapSnapshot(snap: OtaSnapshot): FlashProgress {
  const phase = STATE_TO_PHASE[snap.state];
  return {
    phase,
    percent: Math.round(snap.percent),
    message: stateMessage(snap),
    bytesWritten: snap.bytesSent,
    bytesTotal: snap.bytesTotal,
    phasePercent:
      snap.bytesTotal > 0 && snap.state === "TRANSFERRING"
        ? Math.round((snap.bytesSent / snap.bytesTotal) * 100)
        : undefined,
  };
}
