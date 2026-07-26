/**
 * WebSerial connection layer.
 *
 * Wraps the Web Serial API to provide a simple open/read/write/close
 * interface for connecting to a flight controller via USB.
 */

export interface SerialConnection {
  readable: ReadableStream<Uint8Array>;
  writable: WritableStream<Uint8Array>;
  _writer: WritableStreamDefaultWriter<Uint8Array>;
  close(): Promise<void>;
  info: { usbVendorId?: number; usbProductId?: number };
}

export function isWebSerialSupported(): boolean {
  return typeof navigator !== 'undefined' && 'serial' in navigator;
}

const BAUD_RATES = [57600, 115200, 921600, 460800, 230400] as const;
export type BaudRate = (typeof BAUD_RATES)[number];
export { BAUD_RATES };

const KNOWN_FC_FILTERS: SerialPortFilter[] = [
  { usbVendorId: 0x1209 }, // STM32 bootloader (generic)
  { usbVendorId: 0x0483 }, // STMicroelectronics
  { usbVendorId: 0x26ac }, // 3DRobotics / Pixhawk
  { usbVendorId: 0x2dae }, // Holybro
  { usbVendorId: 0x3162 }, // CubePilot
  { usbVendorId: 0x2341 }, // Arduino (for testing)
];

/**
 * Prompt the user to select a serial port and open it.
 *
 * Returns a SerialConnection object with readable/writable streams.
 * The caller is responsible for reading from the stream and calling close().
 */
export async function openSerial(baudRate: number = 115200): Promise<SerialConnection> {
  if (!isWebSerialSupported()) throw new Error('WebSerial not supported');

  const port = await navigator.serial!.requestPort({ filters: KNOWN_FC_FILTERS });
  await port.open({ baudRate, bufferSize: 4096 });

  const readable = port.readable as ReadableStream<Uint8Array>;
  const writable = port.writable as WritableStream<Uint8Array>;
  const info = port.getInfo();
  const writer = writable.getWriter();

  return {
    readable,
    writable,
    _writer: writer,
    info: { usbVendorId: info.usbVendorId, usbProductId: info.usbProductId },
    async close() {
      try {
        if (readable.locked) {
          const reader = readable.getReader();
          await reader.cancel();
          reader.releaseLock();
        }
      } catch {}
      try {
        await writer.close();
        writer.releaseLock();
      } catch {}
      try {
        await port.close();
      } catch {}
    },
  };
}

/**
 * Write data to a serial connection.
 *
 * Uses the connection's persistent writer — safe to call concurrently;
 * the Streams API queues writes internally.
 */
export async function serialWrite(conn: SerialConnection, data: Uint8Array): Promise<void> {
  await conn._writer.write(data);
}

/**
 * Read loop — reads from serial port and calls onData for each chunk.
 * Returns when the port is closed or an error occurs.
 */
export async function serialReadLoop(conn: SerialConnection, onData: (chunk: Uint8Array) => void): Promise<void> {
  const reader = conn.readable.getReader();
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      if (value) onData(value);
    }
  } catch (e: unknown) {
    if (!(e instanceof Error) || e.name !== 'AbortError') throw e;
  } finally {
    reader.releaseLock();
  }
}
