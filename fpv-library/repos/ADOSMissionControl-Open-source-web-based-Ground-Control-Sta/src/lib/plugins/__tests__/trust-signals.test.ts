/**
 * @license GPL-3.0-only
 *
 * The one trust vocabulary: a plugin resolves the same {@link displayTrustSignals}
 * set on every surface (the install pop-up header, the drone plugin card, the
 * MCP tab), so a first-party or an unsigned plugin never reads as one badge set
 * here and a different one there.
 */

import { describe, it, expect } from "vitest";

import {
  deriveTrustSignals,
  displayTrustSignals,
  isFirstPartySignerId,
} from "../trust-signals";
import { toInstallSummary } from "@/components/plugins/transports/manifest-parse";
import { agentSummaryToManifest } from "@/components/plugins/transports/agent-summary-to-manifest";
import type { ParsedManifest } from "@/components/plugins/transports/manifest-parse";
import type { PluginAgentParseSummary } from "@/lib/agent/plugin-client";

describe("trust-signals · single derivation", () => {
  it("a first-party signer subsumes verified-publisher into first-party", () => {
    const signals = displayTrustSignals({ signerId: "altnautica-2026-A" });
    expect(signals).toContain("signed");
    expect(signals).toContain("first-party");
    expect(signals).not.toContain("verified-publisher");
  });

  it("an unsigned plugin yields no trust signals (never 'unsigned')", () => {
    expect(displayTrustSignals({})).toEqual([]);
  });

  it("a non-first-party signer is only 'signed'", () => {
    expect(displayTrustSignals({ signerId: "some-vendor-key" })).toEqual([
      "signed",
    ]);
  });

  it("deriveTrustSignals keeps verified-publisher for a first-party signer", () => {
    expect(deriveTrustSignals({ signerId: "altnautica-2026-A" })).toEqual([
      "signed",
      "verified-publisher",
      "first-party",
    ]);
  });

  it("isFirstPartySignerId matches only the allowlist form", () => {
    expect(isFirstPartySignerId("altnautica-2026-A")).toBe(true);
    expect(isFirstPartySignerId("altnautica-26-A")).toBe(false);
    expect(isFirstPartySignerId("someone-2026-A")).toBe(false);
    expect(isFirstPartySignerId(undefined)).toBe(false);
  });
});

describe("trust-signals · both pop-up producers route through the derivation", () => {
  const parsed: ParsedManifest = {
    pluginId: "com.example.cam",
    version: "1.0.0",
    name: "Example Cam",
    risk: "medium",
    halves: ["gcs"],
    signerId: "altnautica-2026-A",
    license: "GPL-3.0-or-later",
    permissions: [],
  } as unknown as ParsedManifest;

  it("toInstallSummary stamps the shared display set", () => {
    const summary = toInstallSummary(parsed, "hash");
    expect(summary.trustSignals).toEqual(
      displayTrustSignals({
        signerId: "altnautica-2026-A",
        license: "GPL-3.0-or-later",
      }),
    );
    // First-party + an open license → signed + first-party + open-source.
    expect(summary.trustSignals).toEqual(
      expect.arrayContaining(["signed", "first-party", "open-source"]),
    );
    expect(summary.trustSignals).not.toContain("verified-publisher");
  });

  it("agentSummaryToManifest stamps the same set from the agent parse", () => {
    const agent = {
      ok: true,
      plugin_id: "com.example.cam",
      version: "1.0.0",
      name: "Example Cam",
      description: "",
      author: "",
      license: "GPL-3.0-or-later",
      risk: "medium",
      signer_id: "altnautica-2026-A",
      signed: true,
      halves: ["gcs"],
      permissions: [],
    } as unknown as PluginAgentParseSummary;
    const summary = agentSummaryToManifest(agent);
    expect(summary.trustSignals).toEqual(
      displayTrustSignals({
        signerId: "altnautica-2026-A",
        license: "GPL-3.0-or-later",
      }),
    );
  });

  it("an unsigned manifest yields the same empty set for both surfaces", () => {
    const unsigned = { ...parsed, signerId: undefined, license: undefined };
    const summary = toInstallSummary(
      unsigned as unknown as ParsedManifest,
      "hash",
    );
    expect(summary.trustSignals).toEqual([]);
  });
});
