"use client";

import { ParamTooltip } from "./ParamTooltip";
import type { ParamMetadata } from "@/lib/protocol/param-metadata";

/**
 * Two-line parameter field label: the friendly human name on the first line and
 * the technical param id (monospace, hover for metadata) on the second. This is
 * the canonical label for every FC param form — a flex column so short and long
 * labels stack identically instead of collapsing side-by-side (a plain inline
 * span + the inline-flex `ParamTooltip` would flow onto one line for short
 * labels and only wrap when long).
 *
 * Provide EITHER explicit `label` (friendly) + `param` (mono id) + optional
 * single `meta`, OR the combined `raw` `"PARAM_ID — Friendly Description"` string
 * (built by `useParamLabel().label`) + a `metadata` map for lookup. A bare param
 * name with no friendly text falls back to the metadata human name, or shows the
 * id alone when neither exists.
 */
export function ParamFieldLabel({
  raw,
  label,
  param,
  meta,
  metadata,
}: {
  raw?: string;
  label?: string;
  param?: string;
  meta?: ParamMetadata;
  metadata?: Map<string, ParamMetadata>;
}) {
  let paramId = param;
  let friendly = label;
  if (paramId == null && raw != null) {
    const sep = raw.indexOf(" — ");
    paramId = (sep !== -1 ? raw.slice(0, sep) : raw).trim();
    friendly = friendly ?? (sep !== -1 ? raw.slice(sep + 3).trim() : undefined);
  }
  const resolvedMeta =
    meta ?? (paramId != null ? metadata?.get(paramId) : undefined);
  const friendlyResolved = friendly || resolvedMeta?.humanName;

  return (
    <span className="flex min-w-0 flex-col gap-0.5">
      {friendlyResolved && (
        <span className="text-xs leading-tight text-text-secondary">
          {friendlyResolved}
        </span>
      )}
      <ParamTooltip meta={resolvedMeta}>
        <span className="block cursor-default font-mono text-[9px] leading-tight text-text-tertiary">
          {paramId}
        </span>
      </ParamTooltip>
    </span>
  );
}
