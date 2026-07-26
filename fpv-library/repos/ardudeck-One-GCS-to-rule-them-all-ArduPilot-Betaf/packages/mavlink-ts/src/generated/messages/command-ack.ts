/**
 * Report status of a command. Includes feedback whether the command was executed. The command microservice is documented at https://mavlink.io/en/services/command.html
 * Message ID: 77
 * CRC Extra: 205
 */
export interface CommandAck {
  /** Command ID (of acknowledged command). */
  command: number;
  /** Result of command. */
  result: number;
  /** Also used as result_param1, it can be set with a enum containing the errors reasons of why the command was denied or the progress percentage or 255 if unknown the progress when result is MAV_RESULT_IN_PROGRESS. */
  progress: number;
  /** Additional parameter of the result, example: which parameter of MAV_CMD_NAV_WAYPOINT caused it to be denied. */
  resultParam2: number;
  /** System which requested the command to be executed */
  targetSystem: number;
  /** Component which requested the command to be executed */
  targetComponent: number;
}

export const COMMAND_ACK_ID = 77;
// crc_extra is computed only from non-extension fields. For COMMAND_ACK that's
// "command uint16_t result uint8_t " → 143 (verified against pymavlink).
// Previously this said 205, which came from including extension fields in the
// hash — wrong per the MAVLink spec.
export const COMMAND_ACK_CRC_EXTRA = 143;
// min length = non-extension bytes only (command(2) + result(1) = 3)
// max length = full payload including extensions (10)
export const COMMAND_ACK_MIN_LENGTH = 3;
export const COMMAND_ACK_MAX_LENGTH = 10;

// Wire layout (verified against pymavlink common.xml):
//   command          (uint16) @ 0   (non-extension)
//   result           (uint8)  @ 2   (non-extension)
//   progress         (uint8)  @ 3   (extension)
//   result_param2    (int32)  @ 4   (extension, NOT size-reordered)
//   target_system    (uint8)  @ 8   (extension)
//   target_component (uint8)  @ 9   (extension)
//
// Extension fields stay in declaration order — only non-extension fields are
// size-sorted. The original generator output here treated result_param2 as a
// non-extension and reordered it to offset 0; that broke COMMAND_ACK parsing
// for every standard MAVLink sender (SITL, real ArduPilot, Mission Planner).

export function serializeCommandAck(msg: CommandAck): Uint8Array {
  const buffer = new Uint8Array(10);
  const view = new DataView(buffer.buffer);

  view.setUint16(0, msg.command, true);
  buffer[2] = msg.result & 0xff;
  buffer[3] = msg.progress & 0xff;
  view.setInt32(4, msg.resultParam2, true);
  buffer[8] = msg.targetSystem & 0xff;
  buffer[9] = msg.targetComponent & 0xff;

  return buffer;
}

export function deserializeCommandAck(payload: Uint8Array): CommandAck {
  const view = new DataView(payload.buffer, payload.byteOffset, payload.byteLength);

  // Defensive reads for extension fields: if the sender truncated trailing
  // zero bytes (per MAVLink2 zero-fill rule), payload may be shorter than 10.
  const len = payload.byteLength;
  return {
    command: view.getUint16(0, true),
    result: payload[2] ?? 0,
    progress: len > 3 ? (payload[3] ?? 0) : 0,
    resultParam2: len >= 8 ? view.getInt32(4, true) : 0,
    targetSystem: len > 8 ? (payload[8] ?? 0) : 0,
    targetComponent: len > 9 ? (payload[9] ?? 0) : 0,
  };
}