/**
 * @module history/detail/charts/custom-chart/types
 * @description Shared types for the custom chart builder. Pulled out
 * so the per-channel registry, the data extractor, and the chart
 * components can all reach the same definitions without circular
 * imports.
 * @license GPL-3.0-only
 */

export interface FieldDef {
  key: string;
  label: string;
  unit?: string;
  extract: (data: Record<string, unknown>) => number | undefined;
}

export interface ChannelDef {
  channel: string;
  label: string;
  fields: FieldDef[];
}

export interface TraceConfig {
  id: string;
  channel: string;
  field: string;
  color: string;
}

export const PALETTE = [
  "#3a82ff", "#dff140", "#22c55e", "#ef4444", "#a855f7",
  "#f59e0b", "#06b6d4", "#ec4899", "#84cc16", "#f97316",
];
