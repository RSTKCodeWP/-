"use client";

import { useState, useMemo } from "react";
import { listPresets, listCategories } from "@/lib/presets/presets";
import type { PresetCategory } from "@/lib/presets/types";
import { BuildPresetCard } from "./BuildPresetCard";
import { BuildPresetDetail } from "./BuildPresetDetail";

const CATEGORY_LABELS: Record<PresetCategory, string> = {
  fpv: "FPV",
  "long-range": "Long Range",
  "heavy-lift": "Heavy Lift",
  cine: "Cine",
  racing: "Racing",
  micro: "Micro",
  reference: "ADOS",
};

export function BuildPresetPicker({
  selectedPresetId,
  onSelect,
}: {
  selectedPresetId: string | null;
  onSelect: (presetId: string | null) => void;
}) {
  const [categoryFilter, setCategoryFilter] = useState<PresetCategory | null>(null);
  const [detailPresetId, setDetailPresetId] = useState<string | null>(null);

  const allPresets = useMemo(() => listPresets(), []);
  const categories = useMemo(() => listCategories(), []);

  const filtered = categoryFilter
    ? allPresets.filter((p) => p.category === categoryFilter)
    : allPresets;

  const detailPreset = detailPresetId
    ? allPresets.find((p) => p.id === detailPresetId)
    : null;

  return (
    <div className="space-y-3">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-mono text-text-tertiary uppercase tracking-wider">
          SITL Build Preset
        </h3>
        {selectedPresetId && (
          <button
            onClick={() => onSelect(null)}
            className="text-[10px] text-text-tertiary hover:text-text-secondary cursor-pointer"
          >
            Clear selection
          </button>
        )}
      </div>

      {/* Category filter pills */}
      <div className="flex flex-wrap gap-1">
        <button
          onClick={() => setCategoryFilter(null)}
          className={`px-2 py-0.5 text-[10px] font-mono border transition-colors cursor-pointer ${
            categoryFilter === null
              ? "border-accent-primary text-accent-primary bg-accent-primary/10"
              : "border-border-default text-text-tertiary hover:text-text-secondary hover:border-border-strong"
          }`}
        >
          All
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategoryFilter(categoryFilter === cat ? null : cat)}
            className={`px-2 py-0.5 text-[10px] font-mono border transition-colors cursor-pointer ${
              categoryFilter === cat
                ? "border-accent-primary text-accent-primary bg-accent-primary/10"
                : "border-border-default text-text-tertiary hover:text-text-secondary hover:border-border-strong"
            }`}
          >
            {CATEGORY_LABELS[cat] ?? cat}
          </button>
        ))}
      </div>

      {/* Detail panel */}
      {detailPreset && (
        <BuildPresetDetail
          preset={detailPreset}
          onClose={() => setDetailPresetId(null)}
        />
      )}

      {/* Preset grid */}
      <div className="grid grid-cols-2 gap-2 max-h-[280px] overflow-y-auto pr-1">
        {filtered.map((preset) => (
          <BuildPresetCard
            key={preset.id}
            preset={preset}
            selected={selectedPresetId === preset.id}
            onSelect={() => onSelect(preset.id === selectedPresetId ? null : preset.id)}
            onDetail={() => setDetailPresetId(
              detailPresetId === preset.id ? null : preset.id
            )}
          />
        ))}
      </div>

      {/* Hint */}
      <p className="text-[9px] text-text-tertiary">
        Selecting a preset configures the SITL autopilot with matching frame, battery, and sensor parameters.
        The architecture diagram will populate with the preset&apos;s components.
      </p>
    </div>
  );
}
