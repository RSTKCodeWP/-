import { describe, it, expect } from "vitest";
import {
  deriveTrustSignals,
  displayTrustSignals,
  isFirstParty,
} from "@/lib/plugins/trust-signals";

describe("deriveTrustSignals", () => {
  it("marks a first-party signer as signed + verified-publisher + first-party", () => {
    const signals = deriveTrustSignals({ signerId: "altnautica-2026-A" });
    expect(signals).toEqual(["signed", "verified-publisher", "first-party"]);
  });

  it("marks a non-first-party signer as signed only", () => {
    expect(deriveTrustSignals({ signerId: "community-key-42" })).toEqual([
      "signed",
    ]);
  });

  it("emits no signal when there is no signer", () => {
    expect(deriveTrustSignals({})).toEqual([]);
    expect(deriveTrustSignals({ signerId: "  " })).toEqual([]);
  });

  it("adds open-source for an open license", () => {
    for (const license of [
      "GPL-3.0-or-later",
      "GPL-3.0-only",
      "MIT",
      "Apache-2.0",
      "BSD-3-Clause",
      "CC0-1.0",
    ]) {
      expect(deriveTrustSignals({ license })).toContain("open-source");
    }
  });

  it("does not add open-source for a proprietary license", () => {
    expect(deriveTrustSignals({ license: "Proprietary" })).not.toContain(
      "open-source",
    );
    expect(deriveTrustSignals({ license: undefined })).not.toContain(
      "open-source",
    );
  });

  it("adds vendor-binary when a closed vendor attribution is declared", () => {
    expect(
      deriveTrustSignals({ vendorAttribution: [{ name: "rknn_toolkit" }] }),
    ).toContain("vendor-binary");
    expect(deriveTrustSignals({ vendorAttribution: [] })).not.toContain(
      "vendor-binary",
    );
  });

  it("composes signals from all facts", () => {
    const signals = deriveTrustSignals({
      signerId: "altnautica-2026-A",
      license: "GPL-3.0-or-later",
      vendorAttribution: [{ name: "tensorrt" }],
    });
    expect(signals).toEqual([
      "signed",
      "verified-publisher",
      "first-party",
      "open-source",
      "vendor-binary",
    ]);
  });
});

describe("displayTrustSignals", () => {
  it("drops verified-publisher when first-party is present", () => {
    expect(displayTrustSignals({ signerId: "altnautica-2026-A" })).toEqual([
      "signed",
      "first-party",
    ]);
  });

  it("keeps the full set otherwise", () => {
    expect(displayTrustSignals({ signerId: "community-key" })).toEqual([
      "signed",
    ]);
  });
});

describe("isFirstParty", () => {
  it("is true only for a first-party signer format", () => {
    expect(isFirstParty({ signerId: "altnautica-2026-A" })).toBe(true);
    expect(isFirstParty({ signerId: "altnautica-key" })).toBe(false);
    expect(isFirstParty({})).toBe(false);
  });
});
