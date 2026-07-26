/**
 * @module PoiEditor
 * @description Plan-attached Points of Interest editor panel. Add, label,
 * annotate, reposition, and remove POIs. A POI is a pure GCS planning
 * annotation (a labelled marker with an optional note) — NOT an FC concept — so
 * there is no upload/download, only map rendering and save/load with the plan.
 * Mirrors {@link module:RallyPointEditor}.
 * @license GPL-3.0-only
 */
"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { MapPinned, Trash2, Plus } from "lucide-react";
import { Input } from "@/components/ui/input";
import { usePlanPoiStore, type PointOfInterest } from "@/stores/plan-poi-store";
import { usePlannerStore } from "@/stores/planner-store";

export function PoiEditor() {
  const t = useTranslations("poi");
  // POI placement is the single sticky "poi" tool — keep clicking to drop
  // several points. The panel button is just another way to arm the same tool.
  const activeTool = usePlannerStore((s) => s.activeTool);
  const setActiveTool = usePlannerStore((s) => s.setActiveTool);
  const addingPoi = activeTool === "poi";
  const points = usePlanPoiStore((s) => s.points);
  const selectedId = usePlanPoiStore((s) => s.selectedId);
  const select = usePlanPoiStore((s) => s.select);
  const removePoint = usePlanPoiStore((s) => s.removePoint);
  const updatePoint = usePlanPoiStore((s) => s.updatePoint);
  const clearPoints = usePlanPoiStore((s) => s.clearPoints);

  return (
    <div className="flex flex-col gap-2 px-3 py-2">
      {/* Action buttons */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => setActiveTool(addingPoi ? "select" : "poi")}
          className={`flex items-center gap-1 px-2 py-1 text-[10px] font-mono border cursor-pointer transition-colors ${
            addingPoi
              ? "bg-accent-primary/20 border-accent-primary text-accent-primary"
              : "bg-bg-tertiary border-border-default text-text-secondary hover:text-text-primary"
          }`}
        >
          <Plus size={10} />
          {t("add")}
        </button>
        <button
          onClick={() => clearPoints()}
          disabled={points.length === 0}
          title={t("clear")}
          className="flex items-center gap-1 px-2 py-1 text-[10px] font-mono bg-bg-tertiary border border-border-default text-text-secondary hover:text-status-error disabled:opacity-40 cursor-pointer transition-colors"
        >
          <Trash2 size={10} />
        </button>
      </div>

      {/* POI list */}
      {points.length === 0 ? (
        <p className="text-[10px] text-text-tertiary font-mono py-1">{t("empty")}</p>
      ) : (
        <div className="flex flex-col gap-1.5">
          {points.map((point, idx) => (
            <PoiRow
              key={point.id}
              point={point}
              index={idx}
              selected={point.id === selectedId}
              onSelect={select}
              onUpdate={updatePoint}
              onRemove={removePoint}
            />
          ))}
        </div>
      )}

      {addingPoi && (
        <p className="text-[10px] text-accent-primary font-mono animate-pulse">{t("placeHint")}</p>
      )}
    </div>
  );
}

// ── Individual POI row ────────────────────────────────────────

interface PoiRowProps {
  point: PointOfInterest;
  index: number;
  selected: boolean;
  onSelect: (id: string | null) => void;
  onUpdate: (id: string, update: Partial<PointOfInterest>) => void;
  onRemove: (id: string) => void;
}

function PoiRow({ point, index, selected, onSelect, onUpdate, onRemove }: PoiRowProps) {
  const t = useTranslations("poi");
  const [localLabel, setLocalLabel] = useState(point.label ?? "");
  const [localNote, setLocalNote] = useState(point.note ?? "");
  const [localLat, setLocalLat] = useState(point.lat.toFixed(6));
  const [localLon, setLocalLon] = useState(point.lon.toFixed(6));

  const commitLabel = useCallback(() => {
    const v = localLabel.trim();
    onUpdate(point.id, { label: v.length > 0 ? v : undefined });
  }, [localLabel, point.id, onUpdate]);

  const commitNote = useCallback(() => {
    const v = localNote.trim();
    onUpdate(point.id, { note: v.length > 0 ? v : undefined });
  }, [localNote, point.id, onUpdate]);

  const commitLat = useCallback(() => {
    const v = parseFloat(localLat);
    if (!isNaN(v) && v >= -90 && v <= 90) onUpdate(point.id, { lat: v });
    else setLocalLat(point.lat.toFixed(6));
  }, [localLat, point.id, point.lat, onUpdate]);

  const commitLon = useCallback(() => {
    const v = parseFloat(localLon);
    if (!isNaN(v) && v >= -180 && v <= 180) onUpdate(point.id, { lon: v });
    else setLocalLon(point.lon.toFixed(6));
  }, [localLon, point.id, point.lon, onUpdate]);

  return (
    <div
      onClick={() => onSelect(point.id)}
      className={`flex items-start gap-1.5 p-1.5 border cursor-pointer transition-colors ${
        selected
          ? "bg-accent-primary/10 border-accent-primary"
          : "bg-bg-tertiary/50 border-border-default hover:border-border-strong"
      }`}
    >
      {/* Index badge */}
      <div className="flex items-center justify-center w-5 h-5 shrink-0 mt-0.5">
        <MapPinned size={12} className="text-accent-secondary" />
      </div>
      <div className="flex-1 min-w-0">
        <span className="text-[10px] font-mono font-semibold text-text-secondary">P{index + 1}</span>
        <div className="mt-1 flex flex-col gap-1">
          <Input
            label={t("label")}
            type="text"
            value={localLabel}
            onChange={(e) => setLocalLabel(e.target.value)}
            onBlur={commitLabel}
          />
          <div className="grid grid-cols-2 gap-1">
            <Input
              label="Lat"
              type="number"
              step="0.0001"
              value={localLat}
              onChange={(e) => setLocalLat(e.target.value)}
              onBlur={commitLat}
            />
            <Input
              label="Lon"
              type="number"
              step="0.0001"
              value={localLon}
              onChange={(e) => setLocalLon(e.target.value)}
              onBlur={commitLon}
            />
          </div>
          <Input
            label={t("note")}
            type="text"
            value={localNote}
            onChange={(e) => setLocalNote(e.target.value)}
            onBlur={commitNote}
          />
        </div>
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onRemove(point.id);
        }}
        title={t("remove")}
        className="text-text-tertiary hover:text-status-error transition-colors shrink-0 mt-0.5 cursor-pointer"
      >
        <Trash2 size={12} />
      </button>
    </div>
  );
}
