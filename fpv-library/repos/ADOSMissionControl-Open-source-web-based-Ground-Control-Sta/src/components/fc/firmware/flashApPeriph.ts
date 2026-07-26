/**
 * AP_Periph flash dispatcher.
 *
 * Wires the CAN flash button into a real OTA attempt:
 *   - opens a MAVLink CAN_FORWARD transport on the connected drone so the
 *     existing telemetry link stays up
 *   - constructs a DroneCanClient + DroneCanOtaOrchestrator
 *   - feeds snapshots, node status, and bus traffic into the four
 *     `useDroneCan*` Zustand stores so the debug drawer reflects reality
 *
 * SLCAN remains a manual fallback toggled from the bus setup card; that
 * path lifts in a follow-up commit once the agent side ships a relay.
 *
 * @license GPL-3.0-only
 */

import type { DroneProtocol } from "@/lib/protocol/types/protocol";
import {
  MavlinkCanForwardTransport,
  type CanTransport,
} from "@/lib/protocol/transport/can-transport";
import { enterSlcanMode } from "@/lib/protocol/transport/slcan-flash-arbiter";
import { DroneCanClient } from "@/lib/dronecan/client";
import { DroneCanOtaOrchestrator } from "@/lib/dronecan/ota";
import { ApPeriphManifest } from "@/lib/protocol/firmware/ap-periph-manifest";
import { useDroneCanFlashStore } from "@/stores/dronecan/flash-store";
import { useDroneCanNodeStore } from "@/stores/dronecan/node-store";
import { useDroneCanBusStore } from "@/stores/dronecan/bus-store";
import { useDroneCanRpcTraceStore } from "@/stores/dronecan/rpc-trace-store";
import type { AnyTransferEvent } from "@/lib/dronecan/client-types";

export interface FlashApPeriphParams {
  protocol: DroneProtocol;
  targetNodeId: number;
  board: string;
  channel: string;
  manifest: ApPeriphManifest;
  bus?: 1 | 2;
  /**
   * Transport for the CAN bus during the OTA flow.
   *   - `"can-forward"` (default): MAVLink CAN_FORWARD relay, agent-friendly.
   *   - `"slcan"`: direct SLCAN session on the FC's USB port. Requires a
   *     direct WebSerial connection; arbited via `enterSlcanMode()`.
   */
  transport?: "slcan" | "can-forward";
  /** SLCAN bitrate in bits/s (only used when `transport === "slcan"`). */
  slcanBitrate?: number;
  /** SLCAN auto-revert timeout in seconds (only used when `transport === "slcan"`). */
  slcanTimeoutSec?: number;
}

/**
 * Drive one AP_Periph OTA attempt end-to-end. Returns a disposer that
 * tears down the transport + client + subscriptions when the caller is
 * done. Errors surface as rejected promises so the UI can show a toast.
 */
export async function flashApPeriph(
  params: FlashApPeriphParams,
): Promise<{ dispose: () => Promise<void> }> {
  const {
    protocol,
    targetNodeId,
    board,
    channel,
    manifest,
    bus = 1,
    transport: transportKind = "can-forward",
    slcanBitrate = 1_000_000,
    slcanTimeoutSec = 300,
  } = params;

  // 1. Fetch the firmware payload. Do this BEFORE we mess with the CAN
  //    bus so a 404 doesn't leave the FC in CAN_FORWARD mode.
  const fileBytes = await manifest.downloadFirmware(channel, board);

  // 2. Open the chosen CAN transport. The MAVLink CAN_FORWARD path leaves
  //    the MAVLink link up; the SLCAN path replaces it with a direct
  //    SLCAN session on the same USB port (the arbiter handles the
  //    reboot vs hot-switch handoff per chip family).
  let transport: CanTransport;
  let slcanExit: (() => Promise<void>) | null = null;
  if (transportKind === "slcan") {
    const droneId =
      protocol.getVehicleInfo()?.systemId?.toString() ?? "unknown";
    const session = await enterSlcanMode({
      protocol,
      droneId,
      bus: bus === 2 ? 2 : 1,
      bitrate: slcanBitrate,
      timeoutSec: slcanTimeoutSec,
    });
    transport = session.slcanTransport;
    slcanExit = session.exitFn;
  } else {
    const fwdTransport = new MavlinkCanForwardTransport(protocol, { bus });
    await fwdTransport.open({ bitrate: 1_000_000 });
    transport = fwdTransport;
  }

  // 3. Build a DroneCanClient on top of the transport.
  const client = new DroneCanClient(transport);
  await client.start();

  // 4. Fan client signals into the four Zustand stores.
  const unsubs: Array<() => void> = [];
  unsubs.push(
    client.onNodeStatus((srcNodeId, status) => {
      useDroneCanNodeStore.getState().upsertStatus(srcNodeId, status);
    }),
  );
  unsubs.push(client.onAnyTransfer((evt) => publishTransfer(evt)));

  // 5. Run the OTA orchestrator. Snapshots stream into the flash store
  //    until the run completes or errors out.
  const orchestrator = new DroneCanOtaOrchestrator(client);
  const unsubSnapshots = orchestrator.subscribe((snapshot) => {
    useDroneCanFlashStore.getState().setSnapshot(snapshot);
  });
  unsubs.push(unsubSnapshots);

  try {
    await orchestrator.start({ targetNodeId, fileBytes });
  } finally {
    // Do NOT auto-tear-down — the UI relies on the post-DONE state to
    // surface the "change node id" prompt. The caller invokes dispose()
    // when it leaves the page or starts a new attempt.
  }

  return {
    dispose: async () => {
      for (const off of unsubs) off();
      try {
        await client.stop();
      } catch {
        // Best effort.
      }
      try {
        await transport.close();
      } catch {
        // Best effort.
      }
      if (slcanExit) {
        try {
          await slcanExit();
        } catch {
          // Best effort — the FC's CAN_SLCAN_TIMOUT will auto-revert.
        }
      }
    },
  };
}

/** Map a DroneCAN `AnyTransferEvent` onto the bus + rpc-trace stores. */
function publishTransfer(evt: AnyTransferEvent): void {
  useDroneCanBusStore.getState().pushFrame({
    t: evt.ts,
    dir: "in",
    canId: 0,
    decoded: {
      kind: evt.kind === "message" ? "message" : "service",
      dataTypeId: evt.dataTypeId,
      srcNodeId: evt.srcNodeId,
      dstNodeId: evt.dstNodeId,
      isRequest: evt.kind === "request",
    },
    payload: evt.payload,
    label: evt.typeName,
  });

  useDroneCanRpcTraceStore.getState().pushEvent({
    t: evt.ts,
    direction: "in",
    kind:
      evt.kind === "message"
        ? "broadcast"
        : evt.kind === "request"
          ? "request"
          : "response",
    dataTypeId: evt.dataTypeId,
    dataTypeName: evt.typeName ?? `0x${evt.dataTypeId.toString(16)}`,
    srcNodeId: evt.srcNodeId,
    dstNodeId: evt.dstNodeId,
    ok: true,
  });
}
