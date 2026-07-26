/**
 * @module components/mcp/McpOverview
 * @description The MCP tab overview: a small, verified summary of the operator's
 * connector setup — credential counts (from the live list) and the last recorded
 * activity (from the audit mirror). Only real data (Rule 44); no live
 * connected-client list (the server runs on the operator's own machine, and the
 * hosted tab cannot see its localhost connections).
 * @license GPL-3.0-only
 */

"use client";

import { useTranslations } from "next-intl";
import { KeyRound, Activity, Plus } from "lucide-react";
import { communityApi } from "@/lib/community-api";
import { useConvexSkipQuery } from "@/hooks/use-convex-skip-query";
import { Button } from "@/components/ui/button";
import { timeAgo } from "@/lib/plan-library";
import { useMcpTabStore } from "@/stores/mcp-tab-store";
import type { McpTokenRow } from "./McpConsole";
import type { McpAuditRow } from "./McpAuditLog";

function isActive(r: McpTokenRow): boolean {
  return r.revokedAt == null && (r.expiresAt == null || r.expiresAt > Date.now());
}

export function McpOverview({ rows }: { rows: McpTokenRow[] }) {
  const t = useTranslations("mcp");
  const openGenerate = useMcpTabStore((s) => s.openGenerate);
  const navigate = useMcpTabStore((s) => s.navigate);

  const lastAudit = useConvexSkipQuery(communityApi.mcpTokens.recentAudit, {
    enabled: true,
    args: { limit: 1 },
  }) as McpAuditRow[] | undefined;

  const active = rows.filter(isActive).length;
  const lastActivity = lastAudit && lastAudit.length > 0 ? lastAudit[0].createdAt : null;

  const tiles = [
    { icon: KeyRound, label: t("overview.credentials"), value: String(rows.length) },
    { icon: KeyRound, label: t("overview.active"), value: String(active) },
    {
      icon: Activity,
      label: t("overview.lastActivity"),
      value: lastActivity ? timeAgo(lastActivity) : t("overview.noActivity"),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h2 className="text-base font-semibold text-text-primary">{t("overview.title")}</h2>
        <p className="text-sm text-text-secondary">{t("overview.subtitle")}</p>
      </header>

      <div className="grid gap-3 sm:grid-cols-3">
        {tiles.map(({ icon: Icon, label, value }) => (
          <div key={label} className="flex flex-col gap-1.5 rounded-lg border border-border-default bg-bg-secondary p-4">
            <Icon size={16} className="text-accent-primary" />
            <span className="text-xl font-semibold text-text-primary">{value}</span>
            <span className="text-xs text-text-tertiary">{label}</span>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button icon={<Plus size={16} />} onClick={openGenerate}>
          {t("generateCta")}
        </Button>
        <Button variant="secondary" onClick={() => navigate({ kind: "audit" })}>
          {t("overview.viewAudit")}
        </Button>
      </div>
    </div>
  );
}
