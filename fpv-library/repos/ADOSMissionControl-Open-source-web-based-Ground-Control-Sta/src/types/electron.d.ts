/** A raw UDP/TCP MAVLink endpoint the desktop app opens natively (browsers cannot). */
interface ElectronNetOpenSpec {
  proto: "udp" | "tcp";
  host: string;
  port: number;
  /** UDP only. "listen" binds host:port and learns the peer from the first
   *  datagram (the common autopilot case); "target" sends to a fixed host:port.
   *  Ignored for TCP (always a client connect). */
  mode?: "listen" | "target";
}
interface ElectronNetDataMessage {
  id: string;
  data: Uint8Array;
}
interface ElectronNetCloseMessage {
  id: string;
  reason?: string;
}
/** Native UDP/TCP socket bridge owned by the Electron main process. The renderer
 *  only ever holds an opaque socket id; the real socket never leaves main. */
interface ElectronNetAPI {
  open: (spec: ElectronNetOpenSpec) => Promise<{ id: string }>;
  send: (id: string, data: Uint8Array) => Promise<void>;
  close: (id: string) => Promise<void>;
  /** Subscribe to inbound bytes for any open socket. Returns an unsubscribe. */
  onData: (cb: (msg: ElectronNetDataMessage) => void) => () => void;
  /** Subscribe to socket close/error events. Returns an unsubscribe. */
  onClose: (cb: (msg: ElectronNetCloseMessage) => void) => () => void;
}

interface ElectronAPI {
  isElectron: true;
  platform: "darwin" | "win32" | "linux";
  getVersion: () => Promise<string>;
  minimize: () => Promise<void>;
  maximize: () => Promise<void>;
  close: () => Promise<void>;
  onUpdateAvailable: (cb: (info: { version: string }) => void) => void;
  onUpdateDownloaded: (cb: (info: { version: string }) => void) => void;
  installUpdate: () => Promise<void>;
  /** Native UDP/TCP MAVLink sockets — desktop builds only (absent in browsers). */
  net?: ElectronNetAPI;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

export {};
