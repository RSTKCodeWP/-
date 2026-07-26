// net-sockets.ts — native UDP/TCP MAVLink sockets for the desktop app.
// SPDX-License-Identifier: GPL-3.0-only
//
// A browser sandbox cannot open a raw UDP/TCP socket, so the renderer asks the
// main process (over IPC) to own the socket and relays bytes through it. This is
// the classic GCS UDP/TCP link. Inbound bytes are pushed to the renderer on
// `net:data`; socket close/error is pushed on `net:close`. Sockets are loopback/
// LAN endpoints the operator chose in the connect dialog and are never exposed
// beyond this typed IPC surface.

import { ipcMain, type BrowserWindow } from "electron";
import dgram from "node:dgram";
import net from "node:net";
import { randomUUID } from "node:crypto";

interface OpenSpec {
  proto: "udp" | "tcp";
  host: string;
  port: number;
  mode?: "listen" | "target";
}

interface UdpHandle {
  proto: "udp";
  socket: dgram.Socket;
  /** Where to send GCS→drone bytes: learned from the first datagram (listen)
   *  or the fixed target (target mode). */
  peer: { host: string; port: number } | null;
}
interface TcpHandle {
  proto: "tcp";
  socket: net.Socket;
}
type Handle = UdpHandle | TcpHandle;

let mainWindow: BrowserWindow | null = null;
const handles = new Map<string, Handle>();

function pushToRenderer(channel: string, payload: unknown): void {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(channel, payload);
  }
}

function openSocket(spec: OpenSpec): Promise<{ id: string }> {
  const id = randomUUID();

  if (spec.proto === "udp") {
    return new Promise((resolve, reject) => {
      const socket = dgram.createSocket({ type: "udp4", reuseAddr: true });
      const handle: UdpHandle = {
        proto: "udp",
        socket,
        peer:
          spec.mode === "target" ? { host: spec.host, port: spec.port } : null,
      };

      let settled = false;

      socket.on("message", (msg, rinfo) => {
        // Learn the peer from the first datagram in listen mode (the autopilot
        // sends to us, e.g. `--out=udp:GCS:14550`); keep the fixed target
        // otherwise. Either way relay the bytes up.
        if (handle.peer === null || spec.mode !== "target") {
          handle.peer = { host: rinfo.address, port: rinfo.port };
        }
        pushToRenderer("net:data", { id, data: msg });
      });

      socket.on("error", (err) => {
        if (!settled) {
          settled = true;
          handles.delete(id);
          try {
            socket.close();
          } catch {
            /* ignore */
          }
          reject(err);
          return;
        }
        pushToRenderer("net:close", { id, reason: err.message });
        closeSocket(id);
      });

      if (spec.mode === "target") {
        // No bind needed — the OS assigns an ephemeral source port on first
        // send and replies arrive on it. Ready immediately.
        handles.set(id, handle);
        settled = true;
        resolve({ id });
      } else {
        socket.on("listening", () => {
          settled = true;
          handles.set(id, handle);
          resolve({ id });
        });
        // Bind to all interfaces when host is unspecified / wildcard.
        const bindHost =
          spec.host && spec.host !== "0.0.0.0" ? spec.host : undefined;
        socket.bind(spec.port, bindHost);
      }
    });
  }

  // TCP — connect as a client (the SITL / mavlink-router server case).
  return new Promise((resolve, reject) => {
    let settled = false;
    const socket = net.createConnection({ host: spec.host, port: spec.port });
    socket.on("connect", () => {
      settled = true;
      handles.set(id, { proto: "tcp", socket });
      resolve({ id });
    });
    socket.on("data", (data: Buffer) => {
      pushToRenderer("net:data", { id, data });
    });
    socket.on("error", (err) => {
      if (!settled) {
        settled = true;
        reject(err);
        return;
      }
      pushToRenderer("net:close", { id, reason: err.message });
      closeSocket(id);
    });
    socket.on("close", () => {
      if (handles.has(id)) {
        pushToRenderer("net:close", { id });
        closeSocket(id);
      }
    });
  });
}

function sendSocket(id: string, data: Uint8Array): void {
  const handle = handles.get(id);
  if (!handle) return;
  const buf = Buffer.from(data);
  if (handle.proto === "udp") {
    if (handle.peer) {
      handle.socket.send(buf, handle.peer.port, handle.peer.host);
    }
  } else if (!handle.socket.destroyed) {
    handle.socket.write(buf);
  }
}

function closeSocket(id: string): void {
  const handle = handles.get(id);
  if (!handle) return;
  handles.delete(id);
  try {
    if (handle.proto === "udp") {
      handle.socket.close();
    } else {
      handle.socket.destroy();
    }
  } catch {
    /* ignore */
  }
}

/** Tear down every open socket (called on app shutdown). */
export function closeAllSockets(): void {
  for (const id of [...handles.keys()]) {
    closeSocket(id);
  }
}

/** Register the net IPC handlers and bind pushes to the given window. */
export function setupNetSockets(window: BrowserWindow): void {
  mainWindow = window;
  ipcMain.handle("net:open", (_e, spec: OpenSpec) => openSocket(spec));
  ipcMain.handle("net:send", (_e, id: string, data: Uint8Array) => {
    sendSocket(id, data);
  });
  ipcMain.handle("net:close", (_e, id: string) => {
    closeSocket(id);
  });
}
