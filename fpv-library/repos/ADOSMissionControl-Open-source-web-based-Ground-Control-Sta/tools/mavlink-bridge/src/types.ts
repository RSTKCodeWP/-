// types.ts — shared types for the MAVLink bridge tool
// SPDX-License-Identifier: GPL-3.0-only

/** A network endpoint the bridge is attached to. */
export interface LinkEvent {
  host: string;
  port: number;
}

/** A learned remote UDP peer (listen mode). */
export interface PeerEvent {
  host: string;
  port: number;
}

/** A connected WebSocket client (the GCS). */
export interface WsClientEvent {
  remoteAddress: string;
}

/** A raw binary frame relayed in either direction (zero MAVLink parsing). */
export interface DataEvent {
  data: Buffer;
}

/** Lifecycle events common to every bridge transport. */
export interface BridgeEvents {
  'connected': [LinkEvent];
  'disconnected': [LinkEvent];
  'ws-client-connected': [WsClientEvent];
  'ws-client-disconnected': [WsClientEvent];
  'data': [DataEvent];
  'error': [Error];
}

/** Minimal control surface shared by every bridge transport. */
export interface Bridge {
  start(): void;
  shutdown(): void;
  readonly wsClientCount: number;
}
