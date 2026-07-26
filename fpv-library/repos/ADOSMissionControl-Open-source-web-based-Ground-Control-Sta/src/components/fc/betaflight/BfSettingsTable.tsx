/**
 * @module BfSettingsTable
 * @description Virtualized table of Betaflight CLI settings. Values are the
 * raw CLI text (enum labels / numbers / strings); a setting with enum metadata
 * renders a dropdown, everything else a text field. Sub-component of
 * BfSettingsPanel.
 * @license GPL-3.0-only
 */

"use client";

import { useMemo, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { cn } from "@/lib/utils";
import { Select } from "@/components/ui/select";
import type { SelectOption } from "@/components/ui/select";
import type { ParamMetadata } from "@/lib/protocol/param-metadata";
import type { CliSetting } from "@/lib/protocol/types";

interface BfSettingsTableProps {
  settings: CliSetting[];
  metadata: Map<string, ParamMetadata>;
  modified: Map<string, string>;
  onModify: (name: string, value: string) => void;
  filter: string;
  showModifiedOnly: boolean;
  disabled: boolean;
}

const ROW_HEIGHT = 34;
const GRID_COLS = "minmax(180px, 2fr) minmax(160px, 2fr) minmax(110px, 1fr)";

/** One editable setting cell: a dropdown for enum settings, else a text field. */
function BfSettingControl({ meta, value, disabled, onChange }: {
  meta: ParamMetadata | undefined;
  value: string;
  disabled: boolean;
  onChange: (v: string) => void;
}) {
  const enumOptions = useMemo<SelectOption[] | null>(() => {
    if (!meta?.values || meta.values.size === 0) return null;
    const opts = [...meta.values.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([code, label]) => ({ value: label, label: `${code}: ${label}` }));
    // Keep an out-of-catalog current value selectable (version drift).
    if (!opts.some((o) => o.value === value)) opts.push({ value, label: value });
    return opts;
  }, [meta, value]);

  if (enumOptions) {
    return (
      <Select
        options={enumOptions}
        value={value}
        onChange={onChange}
        disabled={disabled}
        searchable={enumOptions.length > 15}
      />
    );
  }
  return (
    <input
      type="text"
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      className="w-full h-6 bg-bg-tertiary border border-border-default px-1.5 text-xs font-mono text-text-primary focus:outline-none focus:border-accent-primary disabled:opacity-50"
    />
  );
}

export function BfSettingsTable({ settings, metadata, modified, onModify, filter, showModifiedOnly, disabled }: BfSettingsTableProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    let rows = settings;
    if (showModifiedOnly) rows = rows.filter((s) => modified.has(s.name));
    if (filter) {
      const q = filter.toLowerCase();
      rows = rows.filter((s) => s.name.toLowerCase().includes(q));
    }
    return rows;
  }, [settings, filter, showModifiedOnly, modified]);

  const rowVirtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 12,
  });

  return (
    <div ref={parentRef} className="overflow-auto flex-1 border border-border-default">
      <div style={{ height: rowVirtualizer.getTotalSize(), position: "relative" }}>
        {filtered.length === 0 ? (
          <div className="px-3 py-8 text-center text-text-tertiary text-xs">
            {settings.length === 0 ? "No settings loaded" : "No matching settings"}
          </div>
        ) : (
          rowVirtualizer.getVirtualItems().map((vr) => {
            const s = filtered[vr.index];
            const meta = metadata.get(s.name);
            const isMod = modified.has(s.name);
            const value = isMod ? modified.get(s.name)! : s.value;
            const range = meta?.range ? `${meta.range.min} .. ${meta.range.max}` : (meta?.valueType ?? "—");
            return (
              <div
                key={s.name}
                className={cn("grid items-center border-b border-border-default px-3 gap-3", isMod && "bg-status-warning/5")}
                style={{
                  position: "absolute", top: 0, left: 0, width: "100%",
                  height: ROW_HEIGHT, transform: `translateY(${vr.start}px)`,
                  gridTemplateColumns: GRID_COLS,
                }}
              >
                <span className="font-mono text-xs text-text-primary truncate" title={s.name}>{s.name}</span>
                <BfSettingControl meta={meta} value={value} disabled={disabled} onChange={(v) => onModify(s.name, v)} />
                <span className="font-mono text-[10px] text-text-tertiary truncate" title={range}>{range}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
