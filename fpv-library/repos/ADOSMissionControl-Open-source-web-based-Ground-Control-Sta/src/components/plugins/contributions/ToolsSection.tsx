/**
 * @module plugins/contributions/ToolsSection
 * @description The MCP-tools list in the install pop-up's contributions block.
 * Each tool an AI client could invoke through the plugin renders with a
 * safety-class badge, an agent/GCS half chip, its description, and a
 * collapsible input schema — modeled on the MCP tab's plugin detail so the two
 * surfaces read consistently.
 *
 * @license GPL-3.0-only
 */

"use client";

import { Bot } from "lucide-react";
import { useTranslations } from "next-intl";

import { resolveContribLabel } from "@/lib/skills/skill-label";
import { toolSafetyClassBadge } from "@/components/mcp/mcp-shared";
import type { InstallManifestSummary } from "../install-dialog/types";

import { ContribCategory } from "./contribution-primitives";

type Tool = NonNullable<InstallManifestSummary["contributesTools"]>[number];

export function ToolsSection({ tools }: { tools: ReadonlyArray<Tool> }) {
  const t = useTranslations("pluginInstall.review.contributions");
  if (tools.length === 0) return null;
  return (
    <ContribCategory icon={Bot} label={t("tools")} count={tools.length}>
      {tools.map((tool) => (
        <li
          key={`${tool.half ?? ""}:${tool.name}`}
          className="flex flex-col gap-1 rounded-lg border border-border-default/40 bg-bg-tertiary/30 px-3 py-2"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm text-text-primary">
              {tool.name}
            </span>
            {tool.safetyClass ? (
              <span
                className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${toolSafetyClassBadge(tool.safetyClass)}`}
              >
                {tool.safetyClass}
              </span>
            ) : null}
            {tool.half ? (
              <span className="rounded bg-bg-tertiary px-1.5 py-0.5 text-[10px] text-text-tertiary">
                {tool.half === "agent" ? t("agentTool") : t("gcsTool")}
              </span>
            ) : null}
          </div>
          {tool.title && tool.title !== tool.name ? (
            <p className="text-xs text-text-secondary">
              {resolveContribLabel(tool.title)}
            </p>
          ) : null}
          {tool.description ? (
            <p className="text-xs leading-relaxed text-text-tertiary">
              {tool.description}
            </p>
          ) : null}
          {tool.inputSchema ? (
            <details className="text-xs text-text-tertiary">
              <summary className="cursor-pointer select-none">
                {t("inputSchema")}
              </summary>
              <pre className="mt-1 overflow-x-auto rounded bg-bg-tertiary p-2 font-mono text-[11px] text-text-secondary">
                {JSON.stringify(tool.inputSchema, null, 2)}
              </pre>
            </details>
          ) : null}
        </li>
      ))}
    </ContribCategory>
  );
}
