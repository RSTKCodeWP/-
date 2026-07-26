/* A confidence micro-bar with banded fill (DESIGN-SYSTEM §5.2). In the list, two raw
 * decimals side by side are the least-glanceable encoding; a banded bar is pre-attentively
 * comparable down a column. The exact numeric lives in the detail panel. A null value
 * (e.g. CUE_ONLY localization) renders an honest dash, never a zero-length "0% confident". */

interface ConfidenceBarProps {
  value: number | null; // [0, 1] or null for no-data
  label: string; // accessible name (the axis: detection / localization)
  showValue?: boolean; // print the exact numeral beside the bar (detail panel, §7.3)
}

function bandToken(v: number): string {
  if (v >= 0.75) return "bg-st-nominal"; // high
  if (v >= 0.4) return "bg-st-info"; // med
  return "bg-st-caution"; // low — caution, not failure
}

export function ConfidenceBar({ value, label, showValue = false }: ConfidenceBarProps) {
  if (value === null) {
    return (
      <span data-testid="conf-nodata" className="font-mono text-2xs text-text-lo" aria-label={`${label}: no data`}>
        —
      </span>
    );
  }

  const pct = Math.round(value * 100);
  const bar = (
    <span
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={1}
      aria-valuenow={value}
      className="inline-flex h-2 w-9 items-center overflow-hidden rounded-sm bg-surface-3 align-middle"
      title={value.toFixed(2)}
    >
      <span data-testid="conf-fill" className={`h-full ${bandToken(value)}`} style={{ width: `${pct}%` }} />
    </span>
  );

  if (!showValue) return bar;
  return (
    <span className="inline-flex items-center gap-1">
      {bar}
      <span className="font-mono text-2xs tabular-nums text-text-hi">{value.toFixed(2)}</span>
    </span>
  );
}
