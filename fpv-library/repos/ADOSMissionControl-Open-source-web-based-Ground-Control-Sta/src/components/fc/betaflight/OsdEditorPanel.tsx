"use client";

import { useState, useCallback, useMemo } from "react";
import { useToast } from "@/components/ui/toast";
import { useDroneManager } from "@/stores/drone-manager";
import { useTelemetryStore } from "@/stores/telemetry-store";
import {
  OsdElementGrid,
  PRESETS,
  type OsdElement,
  type VideoFormat,
} from "./OsdElementGrid";
import { OsdScreenPreview, FORMAT_ROWS } from "./OsdScreenPreview";
import { ArmedLockOverlay } from "@/components/indicators/ArmedLockOverlay";

const DEFAULT_ELEMENTS: OsdElement[] = [
  { id: "ALTITUDE", label: "Altitude", shortLabel: "ALT", enabled: true, row: 1, col: 1 },
  { id: "BATTVOLT", label: "Battery Voltage", shortLabel: "BATT", enabled: true, row: 1, col: 23 },
  { id: "RSSI", label: "RSSI", shortLabel: "RSSI", enabled: true, row: 0, col: 26 },
  { id: "CURRENT", label: "Current", shortLabel: "AMP", enabled: true, row: 2, col: 23 },
  { id: "SATS", label: "GPS Satellites", shortLabel: "SAT", enabled: true, row: 0, col: 1 },
  { id: "FLTMODE", label: "Flight Mode", shortLabel: "MODE", enabled: true, row: 14, col: 12 },
  { id: "MESSAGES", label: "Messages", shortLabel: "MSG", enabled: true, row: 13, col: 1 },
  { id: "GSPEED", label: "Ground Speed", shortLabel: "GS", enabled: true, row: 8, col: 1 },
  { id: "HORIZON", label: "Horizon", shortLabel: "HOR", enabled: true, row: 7, col: 12 },
  { id: "COMPASS", label: "Compass", shortLabel: "CMP", enabled: true, row: 14, col: 1 },
  { id: "WIND", label: "Wind", shortLabel: "WND", enabled: false, row: 3, col: 1 },
  { id: "ASPEED", label: "Air Speed", shortLabel: "AS", enabled: false, row: 9, col: 1 },
  { id: "VSPEED", label: "Vertical Speed", shortLabel: "VS", enabled: true, row: 10, col: 1 },
  { id: "THROTTLE", label: "Throttle", shortLabel: "THR", enabled: true, row: 8, col: 23 },
  { id: "HEADING", label: "Heading", shortLabel: "HDG", enabled: true, row: 0, col: 12 },
  { id: "HOMEDIST", label: "Home Distance", shortLabel: "DIST", enabled: true, row: 14, col: 23 },
  { id: "HOMEDIR", label: "Home Direction", shortLabel: "DIR", enabled: false, row: 13, col: 23 },
  { id: "POWER", label: "Power", shortLabel: "PWR", enabled: false, row: 3, col: 23 },
  { id: "CELLVOLT", label: "Cell Voltage", shortLabel: "CELL", enabled: false, row: 4, col: 23 },
  { id: "BATBAR", label: "Battery Bar", shortLabel: "BAR", enabled: false, row: 5, col: 23 },
  { id: "ARMING", label: "Arming Status", shortLabel: "ARM", enabled: true, row: 7, col: 12 },
  { id: "CLIMBEFF", label: "Climb Efficiency", shortLabel: "CE", enabled: false, row: 11, col: 1 },
  { id: "EFF", label: "Efficiency", shortLabel: "EFF", enabled: false, row: 12, col: 1 },
  { id: "BATUSED", label: "Battery Used", shortLabel: "mAh", enabled: true, row: 3, col: 23 },
  { id: "CLK", label: "Clock", shortLabel: "CLK", enabled: false, row: 0, col: 22 },
  { id: "ROLL_ANGLE", label: "Roll Angle", shortLabel: "ROLL", enabled: false, row: 6, col: 1 },
  { id: "PITCH_ANGLE", label: "Pitch Angle", shortLabel: "PTCH", enabled: false, row: 7, col: 1 },
];

// Live telemetry preview values for OSD elements
function useLiveTelemetryPreview(): Record<string, string> {
  const vfr = useTelemetryStore((s) => s.vfr);
  const battery = useTelemetryStore((s) => s.battery);
  const gps = useTelemetryStore((s) => s.gps);
  const position = useTelemetryStore((s) => s.position);

  return useMemo(() => {
    const v = vfr.latest();
    const b = battery.latest();
    const g = gps.latest();
    const p = position.latest();
    return {
      ALTITUDE: v ? `${v.alt.toFixed(0)}m` : "ALT",
      BATTVOLT: b ? `${b.voltage.toFixed(1)}V` : "BATT",
      RSSI: "RSSI",
      CURRENT: b ? `${b.current.toFixed(1)}A` : "AMP",
      SATS: g ? `${g.satellites}` : "SAT",
      FLTMODE: "MODE",
      MESSAGES: "MSG",
      GSPEED: v ? `${v.groundspeed.toFixed(1)}` : "GS",
      HORIZON: "HOR",
      COMPASS: p ? `${p.heading.toFixed(0)}°` : "CMP",
      WIND: "WND",
      ASPEED: v ? `${v.airspeed.toFixed(1)}` : "AS",
      VSPEED: v ? `${v.climb.toFixed(1)}` : "VS",
      THROTTLE: v ? `${v.throttle}%` : "THR",
      HEADING: p ? `${p.heading.toFixed(0)}°` : "HDG",
      HOMEDIST: "DIST",
      HOMEDIR: "DIR",
      POWER: b ? `${(b.voltage * b.current).toFixed(0)}W` : "PWR",
      CELLVOLT: "CELL",
      BATBAR: b ? `${b.remaining}%` : "BAR",
      ARMING: "ARM",
      CLIMBEFF: "CE",
      EFF: "EFF",
      BATUSED: b ? `${b.consumed.toFixed(0)}` : "mAh",
      CLK: new Date().toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" }),
      ROLL_ANGLE: "ROLL",
      PITCH_ANGLE: "PTCH",
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vfr.length, battery.length, gps.length, position.length]);
}

export function OsdEditorPanel() {
  const selectedDroneId = useDroneManager((s) => s.selectedDroneId);
  const getSelectedDrone = useDroneManager((s) => s.getSelectedDrone);
  const { toast } = useToast();

  // Per-screen element layouts (screens 1-4)
  const [screenLayouts, setScreenLayouts] = useState<Record<number, OsdElement[]>>({
    1: DEFAULT_ELEMENTS,
    2: DEFAULT_ELEMENTS.map((el) => ({ ...el, enabled: false })),
    3: DEFAULT_ELEMENTS.map((el) => ({ ...el, enabled: false })),
    4: DEFAULT_ELEMENTS.map((el) => ({ ...el, enabled: false })),
  });
  const [activeScreen, setActiveScreen] = useState(1);
  const [saving, setSaving] = useState(false);
  const [showGrid, setShowGrid] = useState(true);
  const [showCommitButton, setShowCommitButton] = useState(false);
  const [videoFormat, setVideoFormat] = useState<VideoFormat>("PAL");
  const [clipboard, setClipboard] = useState<OsdElement[] | null>(null);
  const [livePreview, setLivePreview] = useState(false);

  // Current screen's elements
  const elements = screenLayouts[activeScreen];
  const setElements = useCallback(
    (updater: OsdElement[] | ((prev: OsdElement[]) => OsdElement[])) => {
      setScreenLayouts((prev) => ({
        ...prev,
        [activeScreen]: typeof updater === "function" ? updater(prev[activeScreen]) : updater,
      }));
    },
    [activeScreen],
  );

  const liveTelemetry = useLiveTelemetryPreview();

  const toggleElement = (id: string) => {
    setElements((prev) =>
      prev.map((el) => el.id === id ? { ...el, enabled: !el.enabled } : el)
    );
  };

  const loadPreset = (presetName: string) => {
    const preset = PRESETS[presetName];
    if (!preset) return;

    setElements((prev) =>
      prev.map((el) => {
        const p = preset[el.id];
        if (p) return { ...el, ...p };
        return { ...el, enabled: false };
      })
    );
  };

  const copyScreen = useCallback(() => {
    setClipboard(elements.map((el) => ({ ...el })));
    toast(`Screen ${activeScreen} copied`, "info");
  }, [elements, activeScreen, toast]);

  const pasteScreen = useCallback(() => {
    if (!clipboard) return;
    const maxRow = FORMAT_ROWS[videoFormat] - 1;
    setElements(
      clipboard.map((el) => ({ ...el, row: Math.min(el.row, maxRow) })),
    );
    toast(`Pasted to screen ${activeScreen}`, "success");
  }, [clipboard, activeScreen, videoFormat, setElements, toast]);

  const handleSave = useCallback(async () => {
    const drone = getSelectedDrone();
    if (!drone) return;

    setSaving(true);
    const screenPrefix = `OSD_SCREEN${activeScreen}_`;

    for (const el of elements) {
      const paramName = `${screenPrefix}${el.id}`;
      const value = (el.enabled ? 1 << 15 : 0) | (el.row << 5) | el.col;
      try {
        await drone.protocol.setParameter(paramName, value);
      } catch {
        // Some params might not exist on all firmwares
      }
    }

    setShowCommitButton(true);
    setSaving(false);
    toast("OSD layout saved to flight controller", "success");
  }, [elements, activeScreen, getSelectedDrone, toast]);

  const commitToFlash = useCallback(async () => {
    const drone = getSelectedDrone();
    if (!drone) return;
    try {
      const result = await drone.protocol.commitParamsToFlash();
      if (result.success) {
        setShowCommitButton(false);
        toast("Written to flash — persists after reboot", "success");
      } else {
        toast("Failed to write to flash", "error");
      }
    } catch (err) {
      console.error("[OSD] commitParamsToFlash error:", err);
      toast("Failed to write to flash", "error");
    }
  }, [getSelectedDrone, toast]);

  const handleReset = () => {
    setElements(DEFAULT_ELEMENTS);
  };

  const handleElementMove = useCallback((id: string, row: number, col: number) => {
    setElements((prev) =>
      prev.map((el) => el.id === id ? { ...el, row, col } : el)
    );
  }, [setElements]);

  const enabledElements = elements.filter((el) => el.enabled);

  return (
    <ArmedLockOverlay>
    <div className="h-full flex">
      <OsdElementGrid
        elements={elements}
        activeScreen={activeScreen}
        saving={saving}
        selectedDroneId={selectedDroneId}
        showCommitButton={showCommitButton}
        clipboard={clipboard}
        videoFormat={videoFormat}
        onToggleElement={toggleElement}
        onScreenChange={setActiveScreen}
        onLoadPreset={loadPreset}
        onCopyScreen={copyScreen}
        onPasteScreen={pasteScreen}
        onFormatChange={setVideoFormat}
        onSave={handleSave}
        onCommitFlash={commitToFlash}
        onReset={handleReset}
      />

      <OsdScreenPreview
        enabledElements={enabledElements}
        activeScreen={activeScreen}
        videoFormat={videoFormat}
        selectedDroneId={selectedDroneId}
        livePreview={livePreview}
        showGrid={showGrid}
        liveTelemetry={liveTelemetry}
        onShowGridChange={setShowGrid}
        onLivePreviewChange={setLivePreview}
        onElementMove={handleElementMove}
      />
    </div>
    </ArmedLockOverlay>
  );
}
