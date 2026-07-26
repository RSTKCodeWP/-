/**
 * @module CoordinateWidget
 * @description Consolidated bottom-right planner overlay: the live cursor
 * coordinate + terrain-elevation readout together with the coordinate-format
 * selector, in one card (previously two separate overlays). `bottomOffset`
 * lifts it above the altitude profile when that is present/expanded. The card
 * is pointer-events-none (so cursor tracking passes through to the map) except
 * over the format selector.
 * @license GPL-3.0-only
 */
"use client";

import { useTranslations } from "next-intl";
import { Select } from "@/components/ui/select";
import { FloatingPanel } from "@/components/ui/floating-panel";
import { useSettingsStore } from "@/stores/settings-store";
import type { CoordFormat } from "@/stores/settings-store";
import { useCursorCoord, formatCursorCoord } from "@/lib/planner/cursor-coord";

/** The selectable coordinate formats, in the order shown in the dropdown. */
const FORMATS: readonly CoordFormat[] = ["dd", "dms", "utm", "mgrs"];

/** Narrow an arbitrary Select value back to a CoordFormat (guards a bad value). */
function isCoordFormat(value: string): value is CoordFormat {
  return (FORMATS as readonly string[]).includes(value);
}

export function CoordinateWidget({ bottomOffset }: { bottomOffset?: number }) {
  const t = useTranslations("planner");
  const coordFormat = useSettingsStore((s) => s.coordFormat);
  const setCoordFormat = useSettingsStore((s) => s.setCoordFormat);
  const { coord, elevationText } = useCursorCoord();

  const options = FORMATS.map((f) => ({ value: f, label: t(`coordFormat.${f}`) }));

  return (
    <FloatingPanel
      corner="bottom-right"
      layer="overlay"
      padded={false}
      className="flex flex-col items-end gap-1 px-1.5 py-1 pointer-events-none"
      style={bottomOffset !== undefined ? { bottom: bottomOffset } : undefined}
    >
      {coord && (
        <div className="text-[10px] font-mono text-text-secondary whitespace-nowrap">
          <span className="text-text-primary">
            {formatCursorCoord(coord.lat, coord.lon, coordFormat)}
          </span>
          <span className="ml-2 text-text-tertiary">
            {t("cursorElevation")}: {elevationText}
          </span>
        </div>
      )}
      <div className="pointer-events-auto w-28">
        <Select
          label={<span className="sr-only">{t("coordFormat.label")}</span>}
          options={options}
          value={coordFormat}
          onChange={(value) => {
            if (isCoordFormat(value)) setCoordFormat(value);
          }}
        />
      </div>
    </FloatingPanel>
  );
}
