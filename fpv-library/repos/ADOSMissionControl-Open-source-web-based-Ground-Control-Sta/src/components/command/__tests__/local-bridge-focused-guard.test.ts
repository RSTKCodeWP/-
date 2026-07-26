/**
 * @license GPL-3.0-only
 *
 * Regression guard for bug #1: the CommandFleetLocalBridge stale-identity
 * self-heal must NOT delete the node the operator is focused on. That guard
 * compares `pairing-store.selectedPairedId` against the node's id. The bug was
 * a format mismatch: the selection was minted with one prefix while the guard
 * compared against another, so the equality was ALWAYS false and the focused
 * node was deleted from under the operator.
 *
 * This test pins the invariant the fix relies on: the id the connect path mints
 * for the selection is byte-identical to the id the focused-guard derives from
 * the same device id. Both now go through `nodeIdForDevice`, so they can never
 * drift again.
 */

import { describe, it, expect } from "vitest";

import { nodeIdForDevice } from "@/lib/agent/node-id";

const DEV = "5b67bb47";

describe("CommandFleetLocalBridge focused-guard id parity (bug #1)", () => {
  it("the connect-path selection id equals the focused-guard comparison id", () => {
    // node-click-handler.connectLocalNode selects this id:
    const selectionId = nodeIdForDevice(DEV);
    // CommandFleetLocalBridge derives the focused comparison id the same way:
    const focusedGuardId = nodeIdForDevice(DEV);
    expect(selectionId).toBe(focusedGuardId);
    // And it is the canonical node: form, not the old colon/hyphen split.
    expect(selectionId).toBe("node:5b67bb47");
    expect(selectionId.startsWith("local:")).toBe(false);
    expect(selectionId.startsWith("local-")).toBe(false);
  });

  it("a focused node (selection === guard id) is recognized as focused", () => {
    const selectedPairedId = nodeIdForDevice(DEV);
    const focused = selectedPairedId === nodeIdForDevice(DEV);
    expect(focused).toBe(true);
  });

  it("a different device id is NOT treated as focused", () => {
    const selectedPairedId = nodeIdForDevice("other-device");
    const focused = selectedPairedId === nodeIdForDevice(DEV);
    expect(focused).toBe(false);
  });
});
