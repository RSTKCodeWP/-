/**
 * @module PlanLibraryEmpty
 * @description Empty state for the plan library with call-to-action buttons.
 * @license GPL-3.0-only
 */
"use client";

import { Plus, Import, Download, Loader2 } from "lucide-react";

interface PlanLibraryEmptyProps {
  onNew: () => void;
  onImport: () => void;
  onDownloadFromDrone?: () => void;
  isDownloading?: boolean;
  hasDrone?: boolean;
}

export function PlanLibraryEmpty({ onNew, onImport, onDownloadFromDrone, isDownloading, hasDrone }: PlanLibraryEmptyProps) {
  return (
    <div className="flex flex-col items-center justify-center py-8 px-4 gap-3">
      <p className="text-xs text-text-tertiary text-center">
        No flight plans yet
      </p>
      <button
        onClick={onNew}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-accent-primary border border-accent-primary/30 hover:bg-accent-primary/10 transition-colors cursor-pointer"
      >
        <Plus size={12} />
        Create First Plan
      </button>
      <div className="flex items-center gap-3">
        {onDownloadFromDrone && (
          <button
            onClick={onDownloadFromDrone}
            disabled={isDownloading || !hasDrone}
            className="flex items-center gap-1.5 text-[10px] text-text-tertiary hover:text-text-primary transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            title={!hasDrone ? "Connect a drone first" : "Load mission from drone"}
          >
            {isDownloading ? <Loader2 size={10} className="animate-spin" /> : <Download size={10} />}
            {isDownloading ? "Loading..." : "From Drone"}
          </button>
        )}
        <button
          onClick={onImport}
          className="flex items-center gap-1.5 text-[10px] text-text-tertiary hover:text-text-primary transition-colors cursor-pointer"
        >
          <Import size={10} />
          Import from file
        </button>
      </div>
    </div>
  );
}
