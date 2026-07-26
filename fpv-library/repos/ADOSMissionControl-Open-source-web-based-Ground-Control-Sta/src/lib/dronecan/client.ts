/**
 * @module client
 * @description DroneCAN service client over a `CanTransport`. Owns a
 * `TransferDecoder`, a `TransferIdAllocator`, and the eight DSDL codecs. Sends
 * service requests, correlates responses by transfer ID, decodes inbound
 * `NodeStatus` broadcasts, and serves `uavcan.protocol.file.Read` requests
 * out of a caller-provided buffer for OTA flashing.
 *
 * Transport-agnostic: whatever delivers raw `CanFrame` instances (SLCAN over
 * WebSerial, MAVLink CAN_FRAME relay, or a unit-test mock) is plugged in via
 * the constructor.
 *
 * @license GPL-3.0-only
 */

import type {
  CanFrame,
  CanTransport,
} from "../protocol/transport/can-transport";
import {
  TransferDecoder,
  encodeTransfer,
  type OutboundTransfer,
} from "./transfer-coder";
import { TransferIdAllocator, type TransferKind } from "./transfer-id";
import { DATA_TYPE_IDS, DSDL_SIGNATURES } from "./signatures";
import { DEFAULT_PRIORITY } from "./frame-codec";
import type { NodeStatus } from "./dsdl/node-status";
import {
  encodeGetNodeInfoRequest,
  decodeGetNodeInfoResponse,
  type GetNodeInfoResponse,
} from "./dsdl/get-node-info";
import {
  encodeParamGetSetRequest,
  decodeParamGetSetResponse,
  ValueTag,
  type ParamGetSetRequest,
  type ParamGetSetResponse,
  type Value as ParamValue,
} from "./dsdl/param-getset";
import {
  encodeParamExecuteOpcodeRequest,
  decodeParamExecuteOpcodeResponse,
  type ParamExecuteOpcodeResponse,
} from "./dsdl/param-executeopcode";
import {
  encodeRestartNodeRequest,
  decodeRestartNodeResponse,
  RESTART_NODE_MAGIC,
  type RestartNodeResponse,
} from "./dsdl/restart-node";
import {
  encodeBeginFirmwareUpdateRequest,
  decodeBeginFirmwareUpdateResponse,
  type BeginFirmwareUpdateResponse,
} from "./dsdl/begin-firmware-update";
import {
  encodeGetTransportStatsRequest,
  decodeGetTransportStatsResponse,
  type GetTransportStatsResponse,
} from "./dsdl/get-transport-stats";
import type { GnssFix2 } from "./dsdl/gnss-fix2";
import type { MagneticFieldStrength2 } from "./dsdl/magnetic-field-strength-2";
import { buildEscRawCommandBroadcast } from "./client-broadcasts";
import { PendingRegistry, type PendingKey } from "./client-pending";
import { NodeListenerRegistry } from "./client-subscriptions";
import { TimeoutError } from "./client-errors";
import {
  resolveSignature,
  typeNameFor,
  type AnyTransferEvent,
  type DroneCanClientOptions,
  type FileReadServerHandle,
  type FileReadServerState,
  type ServeFileReadsOptions,
  type ServiceCallOptions,
} from "./client-types";
import { dispatchInboundTransfer } from "./client-inbound";

export type { ParamValue };
export { ValueTag };
export { TimeoutError };
export type {
  AnyTransferEvent,
  DroneCanClientOptions,
  FileReadServerHandle,
  ServeFileReadsOptions,
  ServiceCallOptions,
  TransferKind,
};
export type { GnssFix2 } from "./dsdl/gnss-fix2";
export type { MagneticFieldStrength2 } from "./dsdl/magnetic-field-strength-2";

const DEFAULT_TIMEOUT_MS = 2000;
const DEFAULT_RETRIES = 2;
const DEFAULT_SELF_NODE_ID = 127;

/**
 * DroneCAN service client. One instance per active CAN transport. Multiple
 * subscribers may listen on `onNodeStatus` and `onAnyTransfer`.
 */
export class DroneCanClient {
  private readonly transport: CanTransport;
  private readonly decoder: TransferDecoder;
  private readonly transferIds = new TransferIdAllocator();
  private readonly pending = new PendingRegistry();
  private readonly nodeStatusListeners: Array<
    (srcNodeId: number, status: NodeStatus) => void
  > = [];
  private readonly anyTransferListeners: Array<(evt: AnyTransferEvent) => void> =
    [];
  private readonly fix2Subs = new NodeListenerRegistry<GnssFix2>();
  private readonly mag2Subs = new NodeListenerRegistry<MagneticFieldStrength2>();

  private selfNodeId: number;
  private unsubFrame: (() => void) | null = null;
  private fileServer: FileReadServerState | null = null;
  private started = false;

  constructor(transport: CanTransport, opts: DroneCanClientOptions = {}) {
    this.transport = transport;
    this.selfNodeId = opts.selfNodeId ?? DEFAULT_SELF_NODE_ID;
    this.decoder = new TransferDecoder({
      resolveSignature: (dataTypeId, kind) => resolveSignature(dataTypeId, kind),
    });
    this.decoder.onTransfer((t) =>
      dispatchInboundTransfer(t, {
        pending: this.pending,
        selfNodeId: () => this.selfNodeId,
        fileServer: () => this.fileServer,
        sendFrame: (frame) => this.transport.send(frame),
        emitNodeStatus: (src, status) => this.emitNodeStatus(src, status),
        emitAnyTransfer: (evt) => this.emitAnyTransfer(evt),
        emitFix2: (src, fix) => this.emitFix2(src, fix),
        emitMag2: (src, mag) => this.emitMag2(src, mag),
      }),
    );
  }

  setSelfNodeId(id: number): void {
    this.selfNodeId = id & 0x7f;
  }

  getSelfNodeId(): number {
    return this.selfNodeId;
  }

  /** Open the transport stream and start decoding frames. Idempotent. */
  async start(): Promise<void> {
    if (this.started) return;
    this.started = true;
    this.unsubFrame = this.transport.onFrame((frame) => this.onFrame(frame));
  }

  /** Stop decoding, reject pending requests, and detach. Idempotent. */
  async stop(): Promise<void> {
    if (!this.started) return;
    this.started = false;
    this.unsubFrame?.();
    this.unsubFrame = null;
    this.pending.rejectAll(new Error("DroneCanClient stopped"));
    this.fileServer?.stop();
    this.fileServer = null;
    this.decoder.reset();
    this.fix2Subs.clear();
    this.mag2Subs.clear();
  }

  // ── Subscriptions ─────────────────────────────────────────

  onNodeStatus(cb: (srcNodeId: number, status: NodeStatus) => void): () => void {
    this.nodeStatusListeners.push(cb);
    return () => {
      const i = this.nodeStatusListeners.indexOf(cb);
      if (i >= 0) this.nodeStatusListeners.splice(i, 1);
    };
  }

  onAnyTransfer(cb: (evt: AnyTransferEvent) => void): () => void {
    this.anyTransferListeners.push(cb);
    return () => {
      const i = this.anyTransferListeners.indexOf(cb);
      if (i >= 0) this.anyTransferListeners.splice(i, 1);
    };
  }

  /**
   * Subscribe to decoded `uavcan.equipment.gnss.Fix2` broadcasts from a
   * specific source node. Returns an unsubscribe.
   */
  subscribeFix2(nodeId: number, cb: (fix: GnssFix2) => void): () => void {
    return this.fix2Subs.subscribe(nodeId, cb);
  }

  /**
   * Subscribe to decoded `uavcan.equipment.ahrs.MagneticFieldStrength2`
   * broadcasts from a specific source node. Returns an unsubscribe.
   */
  subscribeMag2(
    nodeId: number,
    cb: (mag: MagneticFieldStrength2) => void,
  ): () => void {
    return this.mag2Subs.subscribe(nodeId, cb);
  }

  /**
   * Broadcast a single `uavcan.equipment.esc.RawCommand` frame. The
   * channel array is encoded as-is (no padding) — callers should pad
   * unused channels with `0` to land their command at the right index.
   */
  async sendEscRawCommand(cmd: number[]): Promise<void> {
    const transferId = this.transferIds.next({
      kind: "msg",
      targetNodeId: 0,
      dataTypeId: DATA_TYPE_IDS.EscRawCommand,
    });
    const { descriptor, payload, event } = buildEscRawCommandBroadcast({
      cmd,
      selfNodeId: this.selfNodeId,
      transferId,
    });
    await this.sendTransfer(descriptor, payload);
    this.emitAnyTransfer(event);
  }

  // ── Service calls ────────────────────────────────────────

  async getNodeInfo(
    targetNodeId: number,
    opts: ServiceCallOptions = {},
  ): Promise<GetNodeInfoResponse> {
    const buf = await this.callService(
      targetNodeId,
      DATA_TYPE_IDS.GetNodeInfo,
      DSDL_SIGNATURES.GetNodeInfo,
      encodeGetNodeInfoRequest(),
      opts,
    );
    return decodeGetNodeInfoResponse(buf);
  }

  paramGet(
    targetNodeId: number,
    index: number,
    opts: ServiceCallOptions = {},
  ): Promise<ParamGetSetResponse> {
    return this.paramGetSet(
      targetNodeId,
      { index, value: { tag: ValueTag.Empty }, name: "" },
      opts,
    );
  }

  paramSet(
    targetNodeId: number,
    name: string,
    value: ParamValue,
    opts: ServiceCallOptions = {},
  ): Promise<ParamGetSetResponse> {
    return this.paramGetSet(targetNodeId, { index: 0, value, name }, opts);
  }

  async paramExecuteOpcode(
    targetNodeId: number,
    opcode: 0 | 1,
    argument: bigint = BigInt(0),
    opts: ServiceCallOptions = {},
  ): Promise<ParamExecuteOpcodeResponse> {
    const buf = await this.callService(
      targetNodeId,
      DATA_TYPE_IDS.paramExecuteOpcode,
      DSDL_SIGNATURES.paramExecuteOpcode,
      encodeParamExecuteOpcodeRequest({ opcode, argument }),
      opts,
    );
    return decodeParamExecuteOpcodeResponse(buf);
  }

  async restart(
    targetNodeId: number,
    opts: ServiceCallOptions = {},
  ): Promise<RestartNodeResponse> {
    const buf = await this.callService(
      targetNodeId,
      DATA_TYPE_IDS.RestartNode,
      DSDL_SIGNATURES.RestartNode,
      encodeRestartNodeRequest({ magic_number: RESTART_NODE_MAGIC }),
      opts,
    );
    return decodeRestartNodeResponse(buf);
  }

  async beginFirmwareUpdate(
    targetNodeId: number,
    sourceNodeId: number,
    imagePath: string,
    opts: ServiceCallOptions = {},
  ): Promise<BeginFirmwareUpdateResponse> {
    const buf = await this.callService(
      targetNodeId,
      DATA_TYPE_IDS.fileBeginFirmwareUpdate,
      DSDL_SIGNATURES.fileBeginFirmwareUpdate,
      encodeBeginFirmwareUpdateRequest({
        source_node_id: sourceNodeId,
        image_file_remote_path: imagePath,
      }),
      opts,
    );
    return decodeBeginFirmwareUpdateResponse(buf);
  }

  async getTransportStats(
    targetNodeId: number,
    opts: ServiceCallOptions = {},
  ): Promise<GetTransportStatsResponse> {
    const buf = await this.callService(
      targetNodeId,
      DATA_TYPE_IDS.GetTransportStats,
      DSDL_SIGNATURES.GetTransportStats,
      encodeGetTransportStatsRequest(),
      opts,
    );
    return decodeGetTransportStatsResponse(buf);
  }

  // ── File-read server (OTA support) ───────────────────────

  serveFileReads(opts: ServeFileReadsOptions): FileReadServerHandle {
    if (this.fileServer) {
      throw new Error("file-read server already registered; call stop() first");
    }
    const state: FileReadServerState = {
      fileData: opts.fileData,
      path: opts.path ?? "a.bin",
      onChunkServed: opts.onChunkServed,
      stop: () => {
        this.fileServer = null;
      },
    };
    this.fileServer = state;
    return { stop: () => state.stop() };
  }

  // ── Internals ────────────────────────────────────────────

  private paramGetSet(
    targetNodeId: number,
    req: ParamGetSetRequest,
    opts: ServiceCallOptions,
  ): Promise<ParamGetSetResponse> {
    return this.callService(
      targetNodeId,
      DATA_TYPE_IDS.paramGetSet,
      DSDL_SIGNATURES.paramGetSet,
      encodeParamGetSetRequest(req),
      opts,
    ).then((buf) => decodeParamGetSetResponse(buf));
  }

  private async callService(
    targetNodeId: number,
    dataTypeId: number,
    signature: bigint,
    payload: Uint8Array,
    opts: ServiceCallOptions,
  ): Promise<Uint8Array> {
    const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    const retries = opts.retries ?? DEFAULT_RETRIES;
    const attempts = retries + 1;
    let lastErr: unknown;
    for (let attempt = 0; attempt < attempts; attempt++) {
      try {
        return await this.sendRequestOnce(
          targetNodeId,
          dataTypeId,
          signature,
          payload,
          timeoutMs,
        );
      } catch (err) {
        lastErr = err;
        if (!(err instanceof TimeoutError)) {
          throw err;
        }
      }
    }
    throw lastErr instanceof Error
      ? lastErr
      : new TimeoutError(`service ${dataTypeId} timed out`);
  }

  private async sendRequestOnce(
    targetNodeId: number,
    dataTypeId: number,
    signature: bigint,
    payload: Uint8Array,
    timeoutMs: number,
  ): Promise<Uint8Array> {
    const transferId = this.transferIds.next({
      kind: "req",
      targetNodeId,
      dataTypeId,
    });
    const key: PendingKey = {
      srcNodeId: targetNodeId,
      dstNodeId: this.selfNodeId,
      dataTypeId,
      transferId,
    };
    const responsePromise = this.pending.register(key, timeoutMs);
    const startedAt = Date.now();
    const typeName = typeNameFor(dataTypeId, "service");
    try {
      await this.sendTransfer(
        {
          priority: DEFAULT_PRIORITY,
          dataTypeId,
          srcNodeId: this.selfNodeId,
          dstNodeId: targetNodeId,
          isRequest: true,
          transferId,
          signature,
          isService: true,
        },
        payload,
      );
      this.emitAnyTransfer({
        ts: startedAt,
        kind: "request",
        srcNodeId: this.selfNodeId,
        dstNodeId: targetNodeId,
        dataTypeId,
        typeName,
        transferId,
        priority: DEFAULT_PRIORITY,
        payload: new Uint8Array(payload),
      });
      return await responsePromise;
    } catch (err) {
      this.pending.discard(key);
      throw err;
    }
  }

  private async sendTransfer(
    descriptor: OutboundTransfer,
    payload: Uint8Array,
  ): Promise<void> {
    const frames = encodeTransfer(payload, descriptor);
    for (const f of frames) {
      const canFrame: CanFrame = {
        id: f.canId,
        extended: true,
        dlc: f.data.length,
        data: f.data,
      };
      await this.transport.send(canFrame);
    }
  }

  private onFrame(frame: CanFrame): void {
    if (!this.started) return;
    this.decoder.push(frame.id, frame.data, frame.timestamp ?? Date.now());
  }

  private emitNodeStatus(srcNodeId: number, status: NodeStatus): void {
    for (const l of this.nodeStatusListeners) {
      try {
        l(srcNodeId, status);
      } catch {
        // listener errors are isolated
      }
    }
  }

  private emitAnyTransfer(evt: AnyTransferEvent): void {
    for (const l of this.anyTransferListeners) {
      try {
        l(evt);
      } catch {
        // listener errors are isolated
      }
    }
  }

  private emitFix2(srcNodeId: number, fix: GnssFix2): void {
    this.fix2Subs.emit(srcNodeId, fix);
  }

  private emitMag2(srcNodeId: number, mag: MagneticFieldStrength2): void {
    this.mag2Subs.emit(srcNodeId, mag);
  }
}
