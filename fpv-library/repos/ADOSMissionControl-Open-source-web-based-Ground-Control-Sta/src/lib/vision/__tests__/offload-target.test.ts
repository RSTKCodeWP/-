import { describe, expect, it } from "vitest";

import type { LocalNode } from "@/stores/local-nodes-store";

import { nodeToOffloadAddr, workstationForOffloadAddr } from "../offload-target";

function ws(hostname: string): LocalNode {
  return { profile: "workstation", hostname } as LocalNode;
}

describe("nodeToOffloadAddr", () => {
  it("uses the paired host with the compute job-API port (:8092), not the control front (:8080)", () => {
    // A workstation paired on the control front :8080 must still be dialed on
    // the compute engine's own port for offload jobs.
    expect(nodeToOffloadAddr({ hostname: "http://192.168.1.5:8080" })).toBe(
      "192.168.1.5:8092",
    );
    expect(nodeToOffloadAddr({ hostname: "192.168.1.5" })).toBe("192.168.1.5:8092");
    expect(nodeToOffloadAddr({ hostname: "ws.local" })).toBe("ws.local:8092");
  });

  it("returns empty for a node with no host (auto-discover)", () => {
    expect(nodeToOffloadAddr({ hostname: "" })).toBe("");
    expect(nodeToOffloadAddr({ hostname: "   " })).toBe("");
  });

  it("round-trips back to the workstation via workstationForOffloadAddr", () => {
    const nodes = [ws("http://10.0.0.9:8080"), ws("10.0.0.10")];
    const addr = nodeToOffloadAddr(nodes[0]!);
    expect(addr).toBe("10.0.0.9:8092");
    expect(workstationForOffloadAddr(nodes, addr)).toBe(nodes[0]);
    expect(workstationForOffloadAddr(nodes, "")).toBeNull();
  });
});
