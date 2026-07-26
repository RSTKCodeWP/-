import { describe, it, expect } from "vitest";
import { isStaleLocalIdentity } from "../stale-local-identity";

describe("isStaleLocalIdentity", () => {
  it("drops a card when the agent reports a different non-empty device id", () => {
    expect(
      isStaleLocalIdentity({ deviceId: "ados-other", paired: true }, "ados-mine"),
    ).toBe(true);
  });

  it("drops a card when the agent reports itself unpaired", () => {
    expect(
      isStaleLocalIdentity({ deviceId: "ados-mine", paired: false }, "ados-mine"),
    ).toBe(true);
  });

  it("keeps the card when the device id matches and it is still paired", () => {
    expect(
      isStaleLocalIdentity({ deviceId: "ados-mine", paired: true }, "ados-mine"),
    ).toBe(false);
  });

  it("keeps the card when the reported id is empty, treating it as no signal", () => {
    // An empty device id must never drop the row even though it differs
    // from the expected id — it means the probe carried no identity.
    expect(
      isStaleLocalIdentity({ deviceId: "", paired: true }, "ados-mine"),
    ).toBe(false);
  });

  it("drops on an explicit unpaired report even when the reported id is empty", () => {
    expect(
      isStaleLocalIdentity({ deviceId: "", paired: false }, "ados-mine"),
    ).toBe(true);
  });
});
