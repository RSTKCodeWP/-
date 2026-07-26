"use client";

/**
 * Betaflight OSD Editor Panel
 *
 * Character-cell grid editor for Betaflight MAX7456 OSD.
 * Supports PAL (30x16), NTSC (30x13), multi-page (4 pages),
 * drag-and-drop element positioning, and MSP OSD config read/write.
 *
 * @license GPL-3.0-only
 */

import { useState, useCallback, useRef } from "react";
import { useToast } from "@/components/ui/toast";
import { useDroneManager } from "@/stores/drone-manager";
import { ArmedLockOverlay } from "@/components/indicators/ArmedLockOverlay";
import { PanelHeader } from "../shared/PanelHeader";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Monitor, Save, HardDrive, Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import type { BfOsdElement, VideoSystem } from "./bf-osd-constants";
import { VIDEO_SYSTEM_OPTIONS, buildDefaultElements, BF_OSD_ELEMENT_DEFS, encodePosition, decodePosition } from "./bf-osd-constants";
import { parseMcmFont } from "./bf-osd-font";
import { BfOsdGrid } from "./BfOsdGrid";
import { BfOsdElementList } from "./BfOsdElementList";

export { encodePosition, decodePosition } from "./bf-osd-constants";

// Betaflight OSD video-system enum (MSP_OSD_CONFIG): 0=AUTO, 1=PAL, 2=NTSC.
const VS_TO_CODE: Record<VideoSystem, number> = { AUTO: 0, PAL: 1, NTSC: 2 };
const CODE_TO_VS = (code: number): VideoSystem => (code === 2 ? "NTSC" : code === 0 ? "AUTO" : "PAL");

export function BfOsdEditorPanel() {
  const selectedDroneId = useDroneManager((s) => s.selectedDroneId);
  const getSelectedDrone = useDroneManager((s) => s.getSelectedDrone);
  const { toast } = useToast();

  const [elements, setElements] = useState<BfOsdElement[]>(buildDefaultElements);
  const [videoSystem, setVideoSystem] = useState<VideoSystem>("PAL");
  const [activePage, setActivePage] = useState(0);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCommitButton, setShowCommitButton] = useState(false);
  const [fontProgress, setFontProgress] = useState<{ done: number; total: number } | null>(null);
  const fontInputRef = useRef<HTMLInputElement>(null);

  // ── Element operations ──────────────────────────────────────

  const updateElement = useCallback(
    (id: number, updates: Partial<BfOsdElement>) => {
      setElements((prev) =>
        prev.map((el) => (el.id === id ? { ...el, ...updates } : el)),
      );
    },
    [],
  );

  const toggleVisibility = useCallback((id: number) => {
    setElements((prev) =>
      prev.map((el) => (el.id === id ? { ...el, visible: !el.visible } : el)),
    );
  }, []);

  const resetAll = useCallback(() => {
    setElements(buildDefaultElements());
    setSelectedId(null);
    toast("Reset all elements to defaults", "info");
  }, [toast]);

  // ── Read from FC ────────────────────────────────────────────

  const handleRead = useCallback(async () => {
    const protocol = getSelectedDrone()?.protocol;
    if (!protocol?.getOsdConfig) {
      setHasLoaded(true);
      toast("Loaded default OSD layout (demo mode)", "info");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const cfg = await protocol.getOsdConfig();
      // Element positions arrive in enum order — index maps to the element id.
      setElements(BF_OSD_ELEMENT_DEFS.map((def, i) => {
        const pos = cfg.items[i]?.position;
        return pos !== undefined
          ? decodePosition(pos, def)
          : { id: def.id, name: def.name, shortLabel: def.shortLabel, x: def.defaultX, y: def.defaultY, page: 0, visible: false };
      }));
      setVideoSystem(CODE_TO_VS(cfg.videoSystem));
      setHasLoaded(true);
      toast("OSD config loaded", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to read OSD config");
    } finally {
      setLoading(false);
    }
  }, [getSelectedDrone, toast]);

  // ── Save to FC ──────────────────────────────────────────────

  const handleSave = useCallback(async () => {
    const protocol = getSelectedDrone()?.protocol;
    if (!protocol?.writeOsdLayout) {
      toast("OSD layout saved (demo mode)", "success");
      setShowCommitButton(true);
      return;
    }
    setSaving(true);
    try {
      const items = elements.map((el) => ({ index: el.id, position: encodePosition(el) }));
      const r = await protocol.writeOsdLayout(items, VS_TO_CODE[videoSystem]);
      if (r.success) {
        setShowCommitButton(true);
        toast("OSD layout saved to flight controller", "success");
      } else {
        toast(r.message, "error");
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to save OSD config", "error");
    } finally {
      setSaving(false);
    }
  }, [getSelectedDrone, elements, videoSystem, toast]);

  // ── Font upload (.mcm) ──────────────────────────────────────

  const handleFontFile = useCallback(async (file: File) => {
    const protocol = getSelectedDrone()?.protocol;
    if (!protocol?.uploadOsdFont) {
      toast("Font upload is not available on this connection", "error");
      return;
    }
    try {
      const { glyphs } = parseMcmFont(await file.text());
      setFontProgress({ done: 0, total: glyphs.length });
      const r = await protocol.uploadOsdFont(glyphs, (done, total) => setFontProgress({ done, total }));
      toast(r.success ? `Uploaded ${glyphs.length} font glyphs` : r.message, r.success ? "success" : "error");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Font upload failed", "error");
    } finally {
      setFontProgress(null);
    }
  }, [getSelectedDrone, toast]);

  // ── Commit to EEPROM ────────────────────────────────────────

  const handleCommitFlash = useCallback(async () => {
    const drone = getSelectedDrone();
    if (!drone) {
      setShowCommitButton(false);
      toast("Written to EEPROM (demo mode)", "success");
      return;
    }
    try {
      const result = await drone.protocol.commitParamsToFlash();
      if (result.success) {
        setShowCommitButton(false);
        toast("Written to EEPROM — persists after reboot", "success");
      } else {
        toast("Failed to write to EEPROM", "error");
      }
    } catch (err) {
      console.error("[BfOSD] commitParamsToFlash error:", err);
      toast("Failed to write to EEPROM", "error");
    }
  }, [getSelectedDrone, toast]);

  // ── Render ────────────────────────────────────────────────

  return (
    <ArmedLockOverlay>
      <div className="h-full flex flex-col gap-3 p-4 overflow-auto">
        <PanelHeader
          title="Betaflight OSD"
          icon={<Monitor size={16} />}
          loading={loading}
          loadProgress={null}
          hasLoaded={hasLoaded}
          onRead={handleRead}
          connected={!!selectedDroneId}
          error={error}
        >
          {hasLoaded && (
            <div className="flex items-center gap-2">
              <Button variant="primary" size="sm" icon={<Save size={12} />} onClick={handleSave} loading={saving} disabled={saving}>
                Save
              </Button>
              {showCommitButton && (
                <Button variant="secondary" size="sm" icon={<HardDrive size={12} />} onClick={handleCommitFlash}>
                  Write to EEPROM
                </Button>
              )}
            </div>
          )}
        </PanelHeader>

        {/* Controls bar */}
        {hasLoaded && (
          <div className="flex items-center gap-3 flex-wrap">
            <div className="w-36">
              <Select label="Video System" options={VIDEO_SYSTEM_OPTIONS} value={videoSystem} onChange={(v) => setVideoSystem(v as VideoSystem)} />
            </div>
            <div className="flex items-center gap-1">
              <span className="text-xs text-text-secondary mr-1">Page:</span>
              {[0, 1, 2, 3].map((p) => (
                <button
                  key={p}
                  onClick={() => setActivePage(p)}
                  className={cn(
                    "w-7 h-7 text-xs font-mono transition-colors",
                    activePage === p
                      ? "bg-accent-primary text-white"
                      : "bg-bg-tertiary text-text-secondary hover:text-text-primary hover:bg-bg-tertiary/80",
                  )}
                >
                  {p + 1}
                </button>
              ))}
            </div>

            {/* Font upload (.mcm) */}
            <input
              ref={fontInputRef}
              type="file"
              accept=".mcm"
              className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFontFile(f); e.target.value = ""; }}
            />
            <Button
              variant="secondary" size="sm" icon={<Upload size={12} />}
              disabled={fontProgress !== null}
              onClick={() => fontInputRef.current?.click()}
            >
              Upload font (.mcm)
            </Button>
            {fontProgress && (
              <span className="text-[11px] font-mono text-text-secondary">
                Uploading {fontProgress.done}/{fontProgress.total} glyphs…
              </span>
            )}
          </div>
        )}

        {/* Main layout: grid + sidebar */}
        {hasLoaded && (
          <div className="flex gap-4 flex-1 min-h-0">
            <BfOsdGrid
              elements={elements}
              activePage={activePage}
              videoSystem={videoSystem}
              selectedId={selectedId}
              onSelectElement={setSelectedId}
              onUpdateElement={updateElement}
              onToggleVisibility={toggleVisibility}
            />
            <BfOsdElementList
              elements={elements}
              selectedId={selectedId}
              onSelectElement={setSelectedId}
              onToggleVisibility={toggleVisibility}
              onResetAll={resetAll}
            />
          </div>
        )}
      </div>
    </ArmedLockOverlay>
  );
}
