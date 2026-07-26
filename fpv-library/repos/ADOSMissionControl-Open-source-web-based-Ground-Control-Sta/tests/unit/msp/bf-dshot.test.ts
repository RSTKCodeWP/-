/**
 * MSP2_SEND_DSHOT_COMMAND (0x3003) encoder tests.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { encodeMspSendDshotCommand } from "@/lib/protocol/msp/encoders/config";
import { DSHOT_CMD, DSHOT_COMMAND_TYPE, DSHOT_ALL_MOTORS } from "@/components/fc/betaflight/bf-dshot-constants";

describe("MSP2_SEND_DSHOT_COMMAND encoder", () => {
  it("encodes [commandType, motorIndex, count, ...commands]", () => {
    const buf = encodeMspSendDshotCommand(DSHOT_COMMAND_TYPE.BLOCKING, 2, [
      DSHOT_CMD.SPIN_DIRECTION_REVERSED,
      DSHOT_CMD.SAVE_SETTINGS,
    ]);
    expect(Array.from(buf)).toEqual([1, 2, 2, 21, 12]);
  });

  it("uses 255 for all motors with an INLINE beacon", () => {
    const buf = encodeMspSendDshotCommand(DSHOT_COMMAND_TYPE.INLINE, DSHOT_ALL_MOTORS, [DSHOT_CMD.BEACON1]);
    expect(Array.from(buf)).toEqual([0, 255, 1, 1]);
  });
});
