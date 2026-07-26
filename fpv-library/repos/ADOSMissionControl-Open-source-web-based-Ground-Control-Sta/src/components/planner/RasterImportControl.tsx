/**
 * @module RasterImportControl
 * @description Compact control for loading a georeferenced GeoTIFF (.tif/.tiff)
 * orthophoto as a base-layer overlay on the planner map. Offers a file picker,
 * a show/hide toggle and a remove button once a raster is loaded, and a clear
 * hint when a file could not be placed. Drives the session-only
 * `raster-overlay-store`; the map layer itself is `RasterOverlay`.
 * @license GPL-3.0-only
 */
"use client";

import { useRef, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Eye, EyeOff, Trash2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRasterOverlayStore } from "@/stores/raster-overlay-store";

export function RasterImportControl() {
  const t = useTranslations("planner");
  const raster = useRasterOverlayStore((s) => s.raster);
  const visible = useRasterOverlayStore((s) => s.visible);
  const loading = useRasterOverlayStore((s) => s.loading);
  const error = useRasterOverlayStore((s) => s.error);
  const loadFromFile = useRasterOverlayStore((s) => s.loadFromFile);
  const toggleVisible = useRasterOverlayStore((s) => s.toggleVisible);
  const clear = useRasterOverlayStore((s) => s.clear);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) await loadFromFile(file);
      // Reset so the same file can be re-selected.
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    [loadFromFile],
  );

  return (
    <div className="border-t border-border-default">
      {/* Header + controls (controls only once a raster is loaded) */}
      <div className="flex items-center justify-between px-3 py-2">
        <span className="text-[11px] font-mono font-semibold text-text-primary">
          {t("raster.label")}
        </span>
        {raster && (
          <div className="flex items-center gap-2">
            <button
              onClick={toggleVisible}
              className="text-text-tertiary hover:text-text-primary transition-colors cursor-pointer"
              aria-label={visible ? t("raster.hide") : t("raster.show")}
            >
              {visible ? <Eye size={12} /> : <EyeOff size={12} />}
            </button>
            <button
              onClick={clear}
              className="text-text-tertiary hover:text-status-error transition-colors cursor-pointer"
              aria-label={t("raster.clear")}
            >
              <Trash2 size={12} />
            </button>
          </div>
        )}
      </div>

      {/* Loaded file name */}
      {raster && raster.name && (
        <div className="px-3 pb-1">
          <span className="block truncate text-[10px] text-text-tertiary" title={raster.name}>
            {raster.name}
          </span>
        </div>
      )}

      {/* Error hint (a file that could not be placed) */}
      {error && (
        <div className="px-3 pb-1.5">
          <span className="text-[10px] text-status-error">{t("raster.errorHint")}</span>
        </div>
      )}

      {/* Empty hint */}
      {!raster && !error && (
        <div className="px-3 pb-1.5">
          <span className="text-[10px] text-text-tertiary">{t("raster.emptyHint")}</span>
        </div>
      )}

      {/* File picker */}
      <div className="px-3 pb-2">
        <input
          ref={fileInputRef}
          type="file"
          accept=".tif,.tiff"
          onChange={handleFileSelect}
          className="hidden"
        />
        <Button
          variant="secondary"
          size="sm"
          icon={<Upload size={12} />}
          onClick={() => fileInputRef.current?.click()}
          className="w-full"
          disabled={loading}
        >
          {loading ? t("raster.loading") : t("raster.chooseFile")}
        </Button>
      </div>
    </div>
  );
}
