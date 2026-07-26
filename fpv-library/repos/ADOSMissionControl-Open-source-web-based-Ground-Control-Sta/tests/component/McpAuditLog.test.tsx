/**
 * Smoke tests for McpAuditLog: the honest empty state (no fabricated rows,
 * Rule 44) and that real events render. The audit query is mocked so the
 * component's rendering + filtering can be exercised without a Convex backend.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "../helpers/intl-wrapper";

const { auditRows } = vi.hoisted(() => ({ auditRows: { current: [] as unknown[] } }));

vi.mock("@/hooks/use-convex-skip-query", () => ({
  useConvexSkipQuery: () => auditRows.current,
}));
vi.mock("@/lib/community-api", () => ({
  communityApi: { mcpTokens: { recentAudit: {} } },
}));

import { McpAuditLog } from "@/components/mcp/McpAuditLog";
import type { McpTokenRow } from "@/components/mcp/McpConsole";

const CREDS: McpTokenRow[] = [
  {
    _id: "c1",
    tokenId: "mct_a",
    scopes: ["read"],
    allowedNodes: [],
    label: "Laptop",
    createdAt: 1,
    expiresAt: null,
    revokedAt: null,
    lastUsedAt: null,
  },
];

describe("McpAuditLog", () => {
  beforeEach(() => {
    auditRows.current = [];
  });

  it("shows the honest empty state when there is no activity", () => {
    renderWithIntl(<McpAuditLog credentials={CREDS} />);
    expect(screen.getByText(/No MCP activity recorded yet/i)).toBeTruthy();
    // the self-reported caveat is always present (Rule 44)
    expect(screen.getByText(/not an independent log/i)).toBeTruthy();
  });

  it("renders real events with their tool and result", () => {
    auditRows.current = [
      {
        _id: "e1",
        tokenId: "mct_a",
        tool: "params.set",
        node: "node-01",
        decision: "confirmed",
        result: "ATC_RAT_RLL_P = 0.135",
        plane: "cloud_relay",
        latencyMs: 42,
        tsUs: 0,
        createdAt: 2,
        argsRedacted: false,
        sensitiveRead: false,
      },
    ];
    renderWithIntl(<McpAuditLog credentials={CREDS} />);
    expect(screen.getByText("params.set")).toBeTruthy();
    expect(screen.getByText(/ATC_RAT_RLL_P/)).toBeTruthy();
    expect(screen.queryByText(/No MCP activity/i)).toBeNull();
  });
});
