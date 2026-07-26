export type FilterMode = "all" | "changed" | "added" | "unchanged";

export const STATUS_STYLES: Record<string, string> = {
  changed: "text-status-warning",
  added: "text-accent-primary",
  unchanged: "text-text-tertiary",
};

export const STATUS_LABELS: Record<string, string> = {
  changed: "Changed",
  added: "New",
  unchanged: "Same",
};

export const FILTER_MODES: FilterMode[] = ["all", "changed", "added", "unchanged"];

export const TH = "px-2 py-1.5 text-text-tertiary font-semibold uppercase tracking-wider text-[10px]";

export function filterLabel(mode: FilterMode, stats: { total: number; changed: number; added: number; unchanged: number }): string {
  switch (mode) {
    case "all": return `All (${stats.total})`;
    case "changed": return `Changed (${stats.changed})`;
    case "added": return `New (${stats.added})`;
    case "unchanged": return `Same (${stats.unchanged})`;
  }
}
