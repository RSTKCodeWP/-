"use client";

/**
 * @module hardware/radio/StatRow
 * @description Single label/value row used by the link-health stats grid.
 * @license GPL-3.0-only
 */

export function StatRow({
  label,
  value,
  valueClass,
  title,
}: {
  label: string;
  value: string;
  valueClass?: string;
  // Optional hover hint shown on the label. Used for rows whose meaning
  // isn't obvious from the label alone (e.g. a thrashing-link counter).
  title?: string;
}) {
  return (
    <div className="flex items-baseline justify-between border-b border-border-default py-1.5">
      <dt
        className="text-xs uppercase tracking-wide text-text-secondary"
        title={title}
      >
        {label}
      </dt>
      <dd className={`font-mono text-sm ${valueClass ?? "text-text-primary"}`}>
        {value}
      </dd>
    </div>
  );
}
