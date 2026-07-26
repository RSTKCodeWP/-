import { beforeEach, describe, expect, it } from "vitest";

import { CONSOLE_MODES, useNavStore } from "./nav";

/* The console-mode store (DESIGN-SYSTEM §11). A tiny global store so the selection spine
 * survives mode switches (independence is the whole point — see §11.3). */

describe("useNavStore", () => {
  beforeEach(() => useNavStore.getState().reset());

  it("defaults to OPS (the live instrument landing mode)", () => {
    expect(useNavStore.getState().mode).toBe("ops");
  });

  it("exposes exactly the four console modes", () => {
    expect(CONSOLE_MODES).toEqual(["ops", "review", "map", "set"]);
  });

  it("setMode changes the active mode", () => {
    useNavStore.getState().setMode("review");
    expect(useNavStore.getState().mode).toBe("review");
  });
});
