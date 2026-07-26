import { describe, it, expect } from "vitest";
import {
  canCredentialCallTool,
  summarizeCredentialReach,
  type ScopeContext,
  type ScopeCredentialLike,
  type ScopeToolDescriptor,
} from "../mcp-scope-model";

const ctx = (over: Partial<ScopeContext> = {}): ScopeContext => ({
  flightEnforced: false,
  fleetMode: false,
  ...over,
});
const cred = (scopes: string[], allowedNodes: string[] = []): ScopeCredentialLike => ({
  scopes,
  allowedNodes,
});
const tool = (over: Partial<ScopeToolDescriptor> & { scope: string }): ScopeToolDescriptor => ({
  name: "t",
  ...over,
});

describe("canCredentialCallTool", () => {
  it("allows a tool whose scope the token holds", () => {
    expect(canCredentialCallTool(cred(["read"]), tool({ scope: "read" }), ctx())).toEqual({
      callable: true,
    });
  });

  it("blocks on scope when the token lacks the tool's group", () => {
    expect(canCredentialCallTool(cred(["read"]), tool({ scope: "admin" }), ctx())).toEqual({
      callable: false,
      reason: "scope",
    });
    // an operate token (read+safe_write+admin) still lacks flight
    expect(
      canCredentialCallTool(
        cred(["read", "safe_write", "admin"]),
        tool({ scope: "flight", affectsFlight: true }),
        ctx({ flightEnforced: true }),
      ),
    ).toEqual({ callable: false, reason: "scope" });
  });

  it("hides a flight tool until enforcement is on, then allows it", () => {
    const flightTool = tool({ scope: "flight", affectsFlight: true });
    const full = cred(["read", "safe_write", "admin", "flight", "destructive"]);
    expect(canCredentialCallTool(full, flightTool, ctx({ flightEnforced: false }))).toEqual({
      callable: false,
      reason: "flight_disabled",
    });
    expect(canCredentialCallTool(full, flightTool, ctx({ flightEnforced: true }))).toEqual({
      callable: true,
    });
  });

  it("hides an agent-mode-only tool in fleet mode", () => {
    const t = tool({ scope: "read", agentModeOnly: true });
    expect(canCredentialCallTool(cred(["read"]), t, ctx({ fleetMode: true }))).toEqual({
      callable: false,
      reason: "agent_mode_only",
    });
    expect(canCredentialCallTool(cred(["read"]), t, ctx({ fleetMode: false }))).toEqual({
      callable: true,
    });
  });

  it("enforces the node allow-list when a node is given", () => {
    const t = tool({ scope: "read" });
    expect(canCredentialCallTool(cred(["read"], ["a"]), t, ctx({ node: "b" }))).toEqual({
      callable: false,
      reason: "node_not_allowed",
    });
    expect(canCredentialCallTool(cred(["read"], ["a"]), t, ctx({ node: "a" }))).toEqual({
      callable: true,
    });
    // an empty allow-list means all nodes
    expect(canCredentialCallTool(cred(["read"], []), t, ctx({ node: "b" }))).toEqual({
      callable: true,
    });
  });

  it("reports the FIRST failing gate (scope before flight)", () => {
    // lacks flight scope AND flight is off — scope is reported first.
    expect(
      canCredentialCallTool(cred(["read"]), tool({ scope: "flight" }), ctx({ flightEnforced: false })),
    ).toEqual({ callable: false, reason: "scope" });
  });
});

describe("summarizeCredentialReach", () => {
  it("counts callable + blocked-by-reason across a tool set", () => {
    const tools: ScopeToolDescriptor[] = [
      tool({ name: "a", scope: "read" }),
      tool({ name: "b", scope: "admin" }), // blocked: scope
      tool({ name: "c", scope: "flight", affectsFlight: true }), // blocked: scope
      tool({ name: "d", scope: "read", agentModeOnly: true }), // blocked: agent_mode_only (fleet)
    ];
    const s = summarizeCredentialReach(cred(["read"]), tools, ctx({ fleetMode: true }));
    expect(s.total).toBe(4);
    expect(s.callable).toBe(1);
    expect(s.blocked).toBe(3);
    expect(s.byReason.scope).toBe(2);
    expect(s.byReason.agent_mode_only).toBe(1);
  });
});
