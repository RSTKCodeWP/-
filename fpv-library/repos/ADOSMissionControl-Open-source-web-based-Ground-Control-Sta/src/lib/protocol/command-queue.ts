/**
 * COMMAND_LONG + COMMAND_ACK tracking queue.
 * Sends MAVLink COMMAND_LONG messages and resolves promises when ACKs arrive.
 */

import type { CommandResult } from "./types";
import { encodeCommandLong } from "./mavlink-encoder";

// MAVLink COMMAND_ACK result codes
export const MAV_RESULT = {
  ACCEPTED: 0,
  TEMPORARILY_REJECTED: 1,
  DENIED: 2,
  UNSUPPORTED: 3,
  FAILED: 4,
  IN_PROGRESS: 5,
  CANCELLED: 6,
} as const;

const RESULT_MESSAGES: Record<number, string> = {
  [MAV_RESULT.ACCEPTED]: "Command accepted",
  [MAV_RESULT.TEMPORARILY_REJECTED]: "Command temporarily rejected",
  [MAV_RESULT.DENIED]: "Command denied",
  [MAV_RESULT.UNSUPPORTED]: "Command unsupported",
  [MAV_RESULT.FAILED]: "Command failed",
  [MAV_RESULT.IN_PROGRESS]: "Command in progress",
  [MAV_RESULT.CANCELLED]: "Command cancelled",
};

interface PendingCommand {
  command: number;
  resolve: (result: CommandResult) => void;
  timer: ReturnType<typeof setTimeout>;
  retryCount: number;
  frame: Uint8Array;
  sendFn: (data: Uint8Array) => void;
  timeoutMs: number;
  // The system id of the vehicle this command was addressed to. Incoming
  // COMMAND_ACKs from a different source sysid are ignored so a co-channel
  // vehicle's ack cannot resolve this drone's pending command.
  targetSys: number;
  // Inputs retained so retries can re-encode the COMMAND_LONG with an
  // incremented confirmation byte rather than resending byte-identical frames.
  encodeArgs: {
    targetSys: number;
    targetComp: number;
    command: number;
    params: [number, number, number, number, number, number, number];
    sysId: number;
    compId: number;
  };
}

export class CommandQueue {
  private pending: Map<number, PendingCommand> = new Map();
  private timeout: number;

  constructor(timeoutMs: number = 3000) {
    this.timeout = timeoutMs;
  }

  /**
   * Send a COMMAND_LONG and wait for the corresponding COMMAND_ACK.
   *
   * @param command — MAV_CMD command ID
   * @param params — 7 float parameters for COMMAND_LONG
   * @param sendFn — transport.send function to transmit the encoded frame
   * @param targetSys — target system ID
   * @param targetComp — target component ID
   * @param sysId — sender system ID
   * @param compId — sender component ID
   * @returns Promise that resolves when ACK is received or times out
   */
  sendCommand(
    command: number,
    params: [number, number, number, number, number, number, number],
    sendFn: (data: Uint8Array) => void,
    targetSys: number,
    targetComp: number,
    sysId: number,
    compId: number,
    timeoutMs?: number,
  ): Promise<CommandResult> {
    const effectiveTimeout = timeoutMs ?? this.timeout;

    // If there's already a pending command with the same ID, reject the old one
    const existing = this.pending.get(command);
    if (existing) {
      clearTimeout(existing.timer);
      existing.resolve({
        success: false,
        resultCode: -1,
        message: "Superseded by new command",
      });
      this.pending.delete(command);
    }

    // First transmission carries confirmation=0. Retries re-encode with an
    // incremented confirmation count, so keep the encode inputs around.
    const encodeArgs = { targetSys, targetComp, command, params, sysId, compId };
    const frame = encodeCommandLong(
      targetSys,
      targetComp,
      command,
      params[0], params[1], params[2], params[3],
      params[4], params[5], params[6],
      sysId,
      compId,
      0,
    );

    return new Promise<CommandResult>((resolve) => {
      // Set up timeout
      const timer = setTimeout(() => {
        this.pending.delete(command);
        resolve({
          success: false,
          resultCode: -1,
          message: `Command ${command} timed out after ${effectiveTimeout}ms`,
        });
      }, effectiveTimeout);

      // Track the pending command
      this.pending.set(command, {
        command, resolve, timer, retryCount: 0,
        frame, sendFn, timeoutMs: effectiveTimeout,
        targetSys, encodeArgs,
      });

      // Send. A transport can throw synchronously (e.g. "Not connected"
      // if the link dropped between the caller's check and here). Fail
      // the command cleanly instead of leaking an unhandled rejection
      // and leaving the promise to hang until the timeout fires.
      try {
        sendFn(frame);
      } catch (err) {
        clearTimeout(timer);
        this.pending.delete(command);
        resolve({
          success: false,
          resultCode: -1,
          message: `Send failed: ${err instanceof Error ? err.message : String(err)}`,
        });
      }
    });
  }

  /**
   * Handle an incoming COMMAND_ACK message.
   * Call this when the MAVLink parser decodes a COMMAND_ACK (msg ID 77).
   *
   * @param command — the command ID being acknowledged
   * @param result — MAV_RESULT code
   * @param sourceSys — the source system id of the ACK frame. When provided,
   *   an ACK whose source does not match the command's target sysid is ignored
   *   so a wrong-vehicle or stale ack cannot resolve this pending command.
   */
  handleAck(command: number, result: number, sourceSys?: number): void {
    const entry = this.pending.get(command);
    if (!entry) return;

    // Drop acks that did not come from the vehicle the command was sent to.
    // A broadcast source (0) is accepted.
    if (sourceSys !== undefined && sourceSys !== 0 && sourceSys !== entry.targetSys) return;

    // IN_PROGRESS: reset timeout, keep waiting for final ACK
    if (result === MAV_RESULT.IN_PROGRESS) {
      clearTimeout(entry.timer);
      entry.timer = setTimeout(() => {
        this.pending.delete(command);
        entry.resolve({
          success: false,
          resultCode: -1,
          message: `Command ${command} timed out after IN_PROGRESS`,
        });
      }, entry.timeoutMs);
      return;
    }

    // TEMPORARILY_REJECTED: auto-retry up to 3 times with 1s delay
    if (result === MAV_RESULT.TEMPORARILY_REJECTED && entry.retryCount < 3) {
      clearTimeout(entry.timer);
      entry.retryCount++;
      // Re-encode the COMMAND_LONG with the confirmation byte set to the
      // retry count. ArduPilot/PX4 distinguish a fresh command from a repeat
      // by this byte; resending confirmation=0 looks like a duplicate first
      // attempt rather than a confirmation.
      const a = entry.encodeArgs;
      entry.frame = encodeCommandLong(
        a.targetSys, a.targetComp, a.command,
        a.params[0], a.params[1], a.params[2], a.params[3],
        a.params[4], a.params[5], a.params[6],
        a.sysId, a.compId,
        entry.retryCount,
      );
      setTimeout(() => {
        // Entry may have been cleared during the delay
        if (!this.pending.has(command)) return;
        // Reset timeout
        entry.timer = setTimeout(() => {
          this.pending.delete(command);
          entry.resolve({
            success: false,
            resultCode: MAV_RESULT.TEMPORARILY_REJECTED,
            message: `Command ${command} temporarily rejected after ${entry.retryCount} retries`,
          });
        }, entry.timeoutMs);
        // Resend. The transport may have dropped during the retry delay
        // and can throw synchronously; fail the command cleanly instead
        // of throwing uncaught inside the timer and leaving the promise
        // pending forever.
        try {
          entry.sendFn(entry.frame);
        } catch (err) {
          clearTimeout(entry.timer);
          this.pending.delete(command);
          entry.resolve({
            success: false,
            resultCode: -1,
            message: `Send failed: ${err instanceof Error ? err.message : String(err)}`,
          });
        }
      }, 1000);
      return;
    }

    // Final result — resolve
    clearTimeout(entry.timer);
    this.pending.delete(command);

    entry.resolve({
      success: result === MAV_RESULT.ACCEPTED,
      resultCode: result,
      message: RESULT_MESSAGES[result] ?? `Unknown result code: ${result}`,
    });
  }

  /** Clear all pending commands (call on disconnect). */
  clear(): void {
    for (const [, entry] of this.pending) {
      clearTimeout(entry.timer);
      entry.resolve({
        success: false,
        resultCode: -1,
        message: "Connection closed",
      });
    }
    this.pending.clear();
  }

  /**
   * Send a COMMAND_LONG without waiting for ACK.
   * Used for commands where the FC may not respond (reset, reboot).
   */
  sendCommandNoAck(
    command: number,
    params: [number, number, number, number, number, number, number],
    sendFn: (data: Uint8Array) => void,
    targetSys: number,
    targetComp: number,
    sysId: number,
    compId: number,
  ): void {
    const frame = encodeCommandLong(
      targetSys, targetComp, command,
      params[0], params[1], params[2], params[3],
      params[4], params[5], params[6],
      sysId, compId,
    );
    sendFn(frame);
  }

  get pendingCount(): number {
    return this.pending.size;
  }

  /** Snapshot of pending commands for diagnostics display */
  getSnapshot(): { command: number; retryCount: number; timestamp: number }[] {
    const result: { command: number; retryCount: number; timestamp: number }[] = [];
    for (const [, entry] of this.pending) {
      result.push({
        command: entry.command,
        retryCount: entry.retryCount,
        timestamp: Date.now(),
      });
    }
    return result;
  }
}
