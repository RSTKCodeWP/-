/**
 * @module fc/betaflight/bf-ports-constants.test
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { bfPortLabel, BF_SERIAL_FUNCTIONS, BF_BAUD_RATES } from "../bf-ports-constants";

describe("bfPortLabel", () => {
  it("labels each serial-port identifier range", () => {
    expect(bfPortLabel(20)).toBe("USB VCP");
    expect(bfPortLabel(30)).toBe("SOFTSERIAL1");
    expect(bfPortLabel(31)).toBe("SOFTSERIAL2");
    expect(bfPortLabel(40)).toBe("LPUART1");
    expect(bfPortLabel(50)).toBe("UART0");
    expect(bfPortLabel(51)).toBe("UART1");
    expect(bfPortLabel(58)).toBe("UART8");
  });
});

describe("BF serial constants", () => {
  it("keeps every function bit inside the U16 mask", () => {
    for (const fn of BF_SERIAL_FUNCTIONS) expect(fn.bit).toBeLessThanOrEqual(15);
  });
  it("orders the baud table so the index is the wire value (Auto=0, 115200=5)", () => {
    expect(BF_BAUD_RATES[0]).toBe("Auto");
    expect(BF_BAUD_RATES[5]).toBe("115200");
    expect(BF_BAUD_RATES.indexOf("921600")).toBe(11);
  });
});
