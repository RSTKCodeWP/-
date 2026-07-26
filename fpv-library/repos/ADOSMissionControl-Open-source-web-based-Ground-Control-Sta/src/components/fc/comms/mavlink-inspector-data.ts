// MAVLink message ID → name (common messages)
export const MSG_NAMES: Record<number, string> = {
  0: "HEARTBEAT",
  1: "SYS_STATUS",
  2: "SYSTEM_TIME",
  4: "PING",
  11: "SET_MODE",
  20: "PARAM_REQUEST_READ",
  21: "PARAM_REQUEST_LIST",
  22: "PARAM_VALUE",
  23: "PARAM_SET",
  24: "GPS_RAW_INT",
  29: "SCALED_PRESSURE",
  30: "ATTITUDE",
  31: "ATTITUDE_QUATERNION",
  32: "LOCAL_POSITION_NED",
  33: "GLOBAL_POSITION_INT",
  35: "RC_CHANNELS_SCALED",
  36: "SERVO_OUTPUT_RAW",
  42: "MISSION_CURRENT",
  44: "MISSION_COUNT",
  47: "MISSION_ACK",
  51: "MISSION_REQUEST_INT",
  62: "NAV_CONTROLLER_OUTPUT",
  65: "RC_CHANNELS",
  69: "MANUAL_CONTROL",
  73: "MISSION_ITEM_INT",
  74: "VFR_HUD",
  76: "COMMAND_LONG",
  77: "COMMAND_ACK",
  87: "POSITION_TARGET_GLOBAL_INT",
  116: "SCALED_IMU2",
  125: "POWER_STATUS",
  126: "SERIAL_CONTROL",
  129: "SCALED_IMU3",
  136: "TERRAIN_REQUEST",
  137: "TERRAIN_DATA",
  147: "BATTERY_STATUS",
  148: "AUTOPILOT_VERSION",
  150: "SENSOR_OFFSETS",
  152: "MEMINFO",
  162: "FENCE_STATUS",
  163: "AHRS",
  164: "SIMSTATE",
  165: "HWSTATUS",
  168: "WIND",
  173: "RANGEFINDER",
  174: "AIRSPEED_AUTOCAL",
  178: "AHRS2",
  193: "EKF_STATUS_REPORT",
  241: "VIBRATION",
  242: "HOME_POSITION",
  253: "STATUSTEXT",
};

export interface DecodedField {
  name: string;
  value: string;
}

export function decodePayload(msgId: number, payload: Uint8Array): DecodedField[] | null {
  const dv = new DataView(payload.buffer, payload.byteOffset, payload.byteLength);
  try {
    switch (msgId) {
      case 0: // HEARTBEAT
        return [
          { name: "type", value: String(payload[0]) },
          { name: "autopilot", value: String(payload[1]) },
          { name: "base_mode", value: `0x${payload[2].toString(16).padStart(2, "0")}` },
          { name: "custom_mode", value: String(dv.getUint32(3, true)) },
          { name: "system_status", value: String(payload[7]) },
          { name: "mavlink_version", value: String(payload[8]) },
        ];
      case 1: // SYS_STATUS
        return [
          { name: "load", value: `${(dv.getUint16(12, true) / 10).toFixed(1)}%` },
          { name: "voltage", value: `${(dv.getUint16(14, true) / 1000).toFixed(2)}V` },
          { name: "current", value: `${(dv.getInt16(16, true) / 100).toFixed(1)}A` },
          { name: "battery_remaining", value: `${dv.getInt8(18)}%` },
        ];
      case 30: // ATTITUDE
        return [
          { name: "roll", value: `${(dv.getFloat32(4, true) * 180 / Math.PI).toFixed(1)}°` },
          { name: "pitch", value: `${(dv.getFloat32(8, true) * 180 / Math.PI).toFixed(1)}°` },
          { name: "yaw", value: `${(dv.getFloat32(12, true) * 180 / Math.PI).toFixed(1)}°` },
        ];
      case 33: // GLOBAL_POSITION_INT
        return [
          { name: "lat", value: `${(dv.getInt32(4, true) / 1e7).toFixed(7)}°` },
          { name: "lon", value: `${(dv.getInt32(8, true) / 1e7).toFixed(7)}°` },
          { name: "alt", value: `${(dv.getInt32(12, true) / 1000).toFixed(1)}m` },
          { name: "relative_alt", value: `${(dv.getInt32(16, true) / 1000).toFixed(1)}m` },
        ];
      case 24: // GPS_RAW_INT
        return [
          { name: "fix_type", value: String(payload[8]) },
          { name: "lat", value: `${(dv.getInt32(9, true) / 1e7).toFixed(7)}°` },
          { name: "lon", value: `${(dv.getInt32(13, true) / 1e7).toFixed(7)}°` },
          { name: "alt", value: `${(dv.getInt32(17, true) / 1000).toFixed(1)}m` },
          { name: "satellites", value: String(payload[25]) },
        ];
      default:
        return null;
    }
  } catch {
    return null;
  }
}

export interface InspectorMessage {
  id: number;
  timestamp: number;
  msgId: number;
  msgName: string;
  systemId: number;
  componentId: number;
  sequence: number;
  payloadLength: number;
  payloadHex: string;
  payloadBytes: Uint8Array;
  direction: "rx" | "tx";
}

export interface MsgRate {
  count: number;
  lastTime: number;
  hz: number;
}
