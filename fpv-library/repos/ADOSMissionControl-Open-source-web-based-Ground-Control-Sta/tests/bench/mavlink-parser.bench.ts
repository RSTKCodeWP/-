import { describe, bench } from 'vitest';
import { MAVLinkParser, crc16, crc16Accumulate } from '@/lib/protocol/mavlink-parser';
import { CRC_EXTRA } from '@/lib/protocol/mavlink-crc-extra';

// Build a valid HEARTBEAT frame for benchmarking
function buildHeartbeatFrame(): Uint8Array {
  const payload = new Uint8Array(9);
  payload[4] = 2; // MAV_TYPE_QUADROTOR
  payload[5] = 3; // MAV_AUTOPILOT_ARDUPILOTMEGA
  payload[6] = 0x90; // base_mode
  payload[8] = 3; // mavlink_version

  const header = new Uint8Array(10);
  header[0] = 0xfd;
  header[1] = payload.length;
  header[4] = 0; // seq
  header[5] = 1; // sysid
  header[6] = 1; // compid
  header[7] = 0; // msgid low

  const crcData = new Uint8Array(9 + payload.length);
  crcData.set(header.subarray(1, 10), 0);
  crcData.set(payload, 9);
  let crc = crc16(crcData, 0, crcData.length);
  crc = crc16Accumulate(CRC_EXTRA.get(0)!, crc);

  const frame = new Uint8Array(10 + payload.length + 2);
  frame.set(header, 0);
  frame.set(payload, 10);
  frame[10 + payload.length] = crc & 0xff;
  frame[10 + payload.length + 1] = (crc >> 8) & 0xff;
  return frame;
}

describe('MAVLink Parser Benchmarks', () => {
  const frame = buildHeartbeatFrame();

  bench('parse single HEARTBEAT frame', () => {
    const parser = new MAVLinkParser();
    parser.onFrame(() => {});
    parser.feed(frame);
  });

  bench('parse 1000 HEARTBEAT frames', () => {
    const parser = new MAVLinkParser();
    parser.onFrame(() => {});
    const batch = new Uint8Array(frame.length * 1000);
    for (let i = 0; i < 1000; i++) {
      batch.set(frame, i * frame.length);
    }
    parser.feed(batch);
  });

  bench('crc16 on 100-byte buffer', () => {
    const data = new Uint8Array(100);
    crc16(data, 0, 100);
  });
});
