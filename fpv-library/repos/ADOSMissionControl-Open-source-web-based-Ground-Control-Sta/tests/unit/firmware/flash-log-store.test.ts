/**
 * Unit tests for the flash log store: bounded ring buffer, version bumps,
 * preserve-across-reconnect semantics, and the self-describing export header.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeEach } from "vitest";
import { useFlashLogStore } from "@/stores/flash-log-store";

function reset() {
  useFlashLogStore.getState().clear();
}

describe("flash-log-store", () => {
  beforeEach(reset);

  it("bumps _version on every log and clear", () => {
    const start = useFlashLogStore.getState()._version;
    useFlashLogStore.getState().log("info", "manager", "a");
    useFlashLogStore.getState().log("debug", "px4", "b");
    expect(useFlashLogStore.getState()._version).toBeGreaterThan(start);
    const beforeClear = useFlashLogStore.getState()._version;
    useFlashLogStore.getState().clear();
    expect(useFlashLogStore.getState()._version).toBeGreaterThan(beforeClear);
  });

  it("bounds memory at the ring-buffer capacity", () => {
    const log = useFlashLogStore.getState().log;
    for (let i = 0; i < 2500; i++) log("info", "manager", `line ${i}`);
    const entries = useFlashLogStore.getState().entries.toArray();
    expect(entries.length).toBe(2000);
    // Oldest dropped, newest retained.
    expect(entries[0].message).toBe("line 500");
    expect(entries[entries.length - 1].message).toBe("line 2499");
  });

  it("preserves the log across a simulated reconnect (only clear() empties)", () => {
    useFlashLogStore.getState().log("info", "px4", "before reboot");
    // A re-enumeration mid-flash must NOT wipe the log.
    useFlashLogStore.getState().log("warning", "manager", "device re-enumerated");
    useFlashLogStore.getState().log("success", "px4", "after reboot");
    expect(useFlashLogStore.getState().entries.length).toBe(3);
  });

  it("buildLogText writes a self-describing header and one line per entry", () => {
    useFlashLogStore.getState().startSession({
      board: "Pixhawk 6X",
      chip: "STM32H743",
      firmware: "PX4 v1.15",
      method: "px4-serial",
    });
    useFlashLogStore.getState().log("error", "px4", "Board ID mismatch", { category: "board_id_mismatch", phase: "chip_detect" });
    useFlashLogStore.getState().log("debug", "px4", "TX 21 20", { rawHex: "21 20" });
    const text = useFlashLogStore.getState().buildLogText();
    expect(text).toContain("ADOS Mission Control — Flash Log");
    expect(text).toContain("board: Pixhawk 6X");
    expect(text).toContain("chip: STM32H743");
    expect(text).toContain("method: px4-serial");
    expect(text).toContain("[ERROR] [px4] (chip_detect) Board ID mismatch");
    expect(text).toContain("21 20");
  });
});
