import { crc16, crc16Accumulate } from '@/lib/protocol/mavlink-parser';
import { CRC_EXTRA } from '@/lib/protocol/mavlink-crc-extra';

export function buildMavlinkFrame(opts: {
  msgId: number;
  payload: Uint8Array;
  systemId?: number;
  componentId?: number;
  sequence?: number;
}): Uint8Array {
  const { msgId, payload, systemId = 1, componentId = 1, sequence = 0 } = opts;
  const header = new Uint8Array(10);
  header[0] = 0xfd; // STX
  header[1] = payload.length;
  header[2] = 0; // inc flags
  header[3] = 0; // cmp flags
  header[4] = sequence;
  header[5] = systemId;
  header[6] = componentId;
  header[7] = msgId & 0xff;
  header[8] = (msgId >> 8) & 0xff;
  header[9] = (msgId >> 16) & 0xff;

  // CRC covers bytes 1..9 + payload
  const crcData = new Uint8Array(9 + payload.length);
  crcData.set(header.subarray(1, 10), 0);
  crcData.set(payload, 9);
  let crc = crc16(crcData, 0, crcData.length);
  const crcExtra = CRC_EXTRA.get(msgId);
  if (crcExtra !== undefined) {
    crc = crc16Accumulate(crcExtra, crc);
  }

  const frame = new Uint8Array(10 + payload.length + 2);
  frame.set(header, 0);
  frame.set(payload, 10);
  frame[10 + payload.length] = crc & 0xff;
  frame[10 + payload.length + 1] = (crc >> 8) & 0xff;
  return frame;
}

/** Build a HEARTBEAT frame (msg 0). */
export function buildHeartbeatFrame(opts?: {
  autopilot?: number;
  type?: number;
  systemId?: number;
}): Uint8Array {
  const payload = new Uint8Array(9);
  const dv = new DataView(payload.buffer);
  dv.setUint32(0, 0, true); // custom_mode
  payload[4] = opts?.type ?? 2; // MAV_TYPE_QUADROTOR
  payload[5] = opts?.autopilot ?? 3; // MAV_AUTOPILOT_ARDUPILOTMEGA
  payload[6] = 0x80 | 0x10; // base_mode (armed + custom)
  dv.setUint8(7, 0); // system_status = UNINIT
  payload[8] = 3; // mavlink_version
  return buildMavlinkFrame({
    msgId: 0,
    payload,
    systemId: opts?.systemId ?? 1,
  });
}
