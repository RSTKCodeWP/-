/**
 * @module OsdPreferencesEditor
 * @description Display preferences (video system, units, sidebars, AHI roll,
 * etc.) for iNav OSD. Sub-component of INavOsdPanel.
 * @license GPL-3.0-only
 */

"use client";

import { Select } from "@/components/ui/select";
import type { INavOsdPreferences } from "@/lib/protocol/msp/msp-decoders-inav";

const VIDEO_SYSTEM_OPTIONS = [
  { value: "0", label: "Auto" },
  { value: "1", label: "PAL" },
  { value: "2", label: "NTSC" },
];

const UNITS_OPTIONS = [
  { value: "0", label: "Imperial" },
  { value: "1", label: "Metric" },
  { value: "2", label: "UK" },
  { value: "3", label: "Aviation" },
];

const ENERGY_UNIT_OPTIONS = [
  { value: "0", label: "mAh" },
  { value: "1", label: "Wh" },
];

const CROSSHAIRS_OPTIONS = [
  { value: "0", label: "Default" },
  { value: "1", label: "Crosshairs 1" },
  { value: "2", label: "Crosshairs 2" },
  { value: "3", label: "Crosshairs 3" },
];

const SIDEBAR_SCROLL_OPTIONS = [
  { value: "0", label: "None" },
  { value: "1", label: "Altitude" },
  { value: "2", label: "Ground speed" },
  { value: "3", label: "Home distance" },
  { value: "4", label: "Moving direction" },
  { value: "5", label: "Current" },
  { value: "6", label: "Pitch angle" },
  { value: "7", label: "Roll angle" },
  { value: "8", label: "GPS accuracy" },
];

const ADSB_WARNING_STYLE_OPTIONS = [
  { value: "0", label: "None" },
  { value: "1", label: "Text" },
  { value: "2", label: "Symbol" },
];

interface OsdPreferencesEditorProps {
  preferences: INavOsdPreferences | null;
  onUpdate: <K extends keyof INavOsdPreferences>(
    key: K,
    value: INavOsdPreferences[K],
  ) => void;
}

export function OsdPreferencesEditor({
  preferences,
  onUpdate,
}: OsdPreferencesEditorProps) {
  if (!preferences) {
    return (
      <p className="text-[11px] text-text-tertiary">
        No preference data returned by FC.
      </p>
    );
  }
  return (
    <div className="space-y-3">
      <Row label="Video system">
        <Select
          value={String(preferences.videoSystem)}
          onChange={(v) => onUpdate("videoSystem", parseInt(v, 10))}
          options={VIDEO_SYSTEM_OPTIONS}
        />
      </Row>
      <Row label="Units">
        <Select
          value={String(preferences.units)}
          onChange={(v) => onUpdate("units", parseInt(v, 10))}
          options={UNITS_OPTIONS}
        />
      </Row>
      <Row label="Energy unit">
        <Select
          value={String(preferences.statsEnergyUnit)}
          onChange={(v) => onUpdate("statsEnergyUnit", parseInt(v, 10))}
          options={ENERGY_UNIT_OPTIONS}
        />
      </Row>
      <Row label="Crosshairs style">
        <Select
          value={String(preferences.crosshairsStyle)}
          onChange={(v) => onUpdate("crosshairsStyle", parseInt(v, 10))}
          options={CROSSHAIRS_OPTIONS}
        />
      </Row>
      <Row label="Left sidebar">
        <Select
          value={String(preferences.leftSidebarScroll)}
          onChange={(v) => onUpdate("leftSidebarScroll", parseInt(v, 10))}
          options={SIDEBAR_SCROLL_OPTIONS}
        />
      </Row>
      <Row label="Right sidebar">
        <Select
          value={String(preferences.rightSidebarScroll)}
          onChange={(v) => onUpdate("rightSidebarScroll", parseInt(v, 10))}
          options={SIDEBAR_SCROLL_OPTIONS}
        />
      </Row>
      <Row label="ADS-B warning style">
        <Select
          value={String(preferences.adsbWarningStyle)}
          onChange={(v) => onUpdate("adsbWarningStyle", parseInt(v, 10))}
          options={ADSB_WARNING_STYLE_OPTIONS}
        />
      </Row>
      <Row label="Voltage decimals">
        <input
          type="number"
          min={0}
          max={1}
          value={preferences.mainVoltageDecimals}
          onChange={(e) =>
            onUpdate("mainVoltageDecimals", parseInt(e.target.value, 10) || 0)
          }
          className="w-28 bg-bg-tertiary border border-border-default rounded px-2 py-1 text-[11px] font-mono text-text-primary text-right"
        />
      </Row>
      <Row label="Reverse AHI roll">
        <ToggleButton
          on={preferences.ahiReverseRoll !== 0}
          onClick={() =>
            onUpdate("ahiReverseRoll", preferences.ahiReverseRoll ? 0 : 1)
          }
        />
      </Row>
      <Row label="Sidebar scroll arrows">
        <ToggleButton
          on={preferences.sidebarScrollArrows !== 0}
          onClick={() =>
            onUpdate(
              "sidebarScrollArrows",
              preferences.sidebarScrollArrows ? 0 : 1,
            )
          }
        />
      </Row>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-[11px] text-text-secondary shrink-0 w-44">{label}</span>
      {children}
    </div>
  );
}

function ToggleButton({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`text-[11px] px-3 py-1 rounded border ${
        on
          ? "border-accent-primary bg-accent-primary/20 text-accent-primary"
          : "border-border-default text-text-secondary"
      }`}
    >
      {on ? "Yes" : "No"}
    </button>
  );
}
