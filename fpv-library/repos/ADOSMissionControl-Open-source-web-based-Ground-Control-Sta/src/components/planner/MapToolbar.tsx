/**
 * @module MapToolbar
 * @description Floating vertical tool dock for the mission planner map.
 * Provides tool selection (select, waypoint, polygon, circle, measure),
 * undo/redo, and clear-all actions.
 * @license GPL-3.0-only
 */
"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  MousePointer2, MapPin, Pentagon, Circle, Ruler,
  Undo2, Redo2, Trash2, HelpCircle, X,
  ArrowUpFromLine, ArrowDownToLine, CircleDot, Crosshair, Flag, Target,
  Layers, CloudDownload, MapPinned,
} from "lucide-react";
import { Tooltip } from "@/components/ui/tooltip";
import { cn, isElectron } from "@/lib/utils";
import type { PlannerTool } from "@/lib/types";
import { PLANNER_SHORTCUTS, shortcutKeyForTool, type PlannerShortcut } from "@/lib/planner-shortcuts";

interface MapToolbarProps {
  activeTool: PlannerTool;
  onToolChange: (tool: PlannerTool) => void;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onClearAll: () => void;
  onToggleOverlays?: () => void;
  overlayPanelOpen?: boolean;
  onToggleDownload?: () => void;
  downloadPanelOpen?: boolean;
}

// `labelKey` is a `planner` i18n key; the shortcut letter is derived from the
// single PLANNER_SHORTCUTS table so the dock, the help popover, and the palette
// never drift apart.
type ToolDef = { id: PlannerTool; icon: typeof MapPin; labelKey: string };

const navTools: ToolDef[] = [
  { id: "select", icon: MousePointer2, labelKey: "shortcuts.select" },
];

const placementTools: ToolDef[] = [
  { id: "waypoint", icon: MapPin, labelKey: "shortcuts.waypoint" },
  { id: "takeoff", icon: ArrowUpFromLine, labelKey: "shortcuts.takeoff" },
  { id: "land", icon: ArrowDownToLine, labelKey: "shortcuts.land" },
  { id: "loiter", icon: CircleDot, labelKey: "shortcuts.loiter" },
  { id: "roi", icon: Crosshair, labelKey: "shortcuts.roi" },
  { id: "rally", icon: Flag, labelKey: "shortcuts.rally" },
  { id: "poi", icon: MapPinned, labelKey: "shortcuts.poi" },
];

const datumTools: ToolDef[] = [
  { id: "datum", icon: Target, labelKey: "shortcuts.datum" },
];

const drawingTools: ToolDef[] = [
  { id: "polygon", icon: Pentagon, labelKey: "shortcuts.polygon" },
  { id: "circle", icon: Circle, labelKey: "shortcuts.circle" },
  { id: "measure", icon: Ruler, labelKey: "shortcuts.measure" },
];

const toolGroups: ToolDef[][] = [navTools, placementTools, datumTools, drawingTools];

/** Format a shortcut's key for display, e.g. "V", "⌘Z", "⌘⇧Z". */
function formatShortcutKey(s: PlannerShortcut): string {
  const mods = `${s.meta ? "⌘" : ""}${s.shift ? "⇧" : ""}`;
  const key = s.key.length === 1 ? s.key.toUpperCase() : s.key;
  return `${mods}${key}`;
}

function ToolButton({
  active,
  disabled,
  onClick,
  children,
  tooltip,
}: {
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
  tooltip: string;
}) {
  return (
    <Tooltip content={tooltip} position="right">
      <button
        onClick={onClick}
        disabled={disabled}
        // Icon-only control: the visible tooltip text is also the button's
        // accessible name, so screen readers announce the same label sighted
        // users see on hover.
        aria-label={tooltip}
        className={cn(
          "w-8 h-8 flex items-center justify-center rounded-md transition-colors cursor-pointer",
          "disabled:opacity-30 disabled:cursor-not-allowed",
          active
            ? "bg-accent-primary/20 text-accent-primary"
            : "text-text-secondary hover:text-text-primary hover:bg-bg-tertiary"
        )}
      >
        {children}
      </button>
    </Tooltip>
  );
}

export function MapToolbar({
  activeTool,
  onToolChange,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onClearAll,
  onToggleOverlays,
  overlayPanelOpen,
  onToggleDownload,
  downloadPanelOpen,
}: MapToolbarProps) {
  const t = useTranslations("planner");
  return (
    <div className="absolute top-24 left-3 z-[1000] flex flex-col gap-1 p-1 bg-bg-secondary/90 backdrop-blur-sm border border-border-default rounded-lg">
      {toolGroups.map((group, gi) => (
        <div key={gi} className="flex flex-col">
          {gi > 0 && <div className="h-px bg-border-default" />}
          {group.map((tool) => {
            const key = shortcutKeyForTool(tool.id);
            const label = t(tool.labelKey);
            return (
              <ToolButton
                key={tool.id}
                active={activeTool === tool.id}
                onClick={() => onToolChange(tool.id)}
                tooltip={key ? `${label} (${key.toUpperCase()})` : label}
              >
                <tool.icon size={16} />
              </ToolButton>
            );
          })}
        </div>
      ))}

      <div className="h-px bg-border-default" />

      <ToolButton
        disabled={!canUndo}
        onClick={onUndo}
        tooltip={t("undo")}
      >
        <Undo2 size={16} />
      </ToolButton>
      <ToolButton
        disabled={!canRedo}
        onClick={onRedo}
        tooltip={t("redo")}
      >
        <Redo2 size={16} />
      </ToolButton>

      <div className="h-px bg-border-default" />

      <ToolButton onClick={onClearAll} tooltip={t("clearAll")}>
        <Trash2 size={16} />
      </ToolButton>

      <div className="h-px bg-border-default" />

      {onToggleOverlays && (
        <ToolButton
          active={overlayPanelOpen}
          onClick={onToggleOverlays}
          tooltip={`${t("shortcuts.overlays")} (L)`}
        >
          <Layers size={16} />
        </ToolButton>
      )}

      {onToggleDownload && (
        <ToolButton
          active={downloadPanelOpen}
          onClick={onToggleDownload}
          tooltip={t("downloadTiles")}
        >
          <CloudDownload size={16} />
        </ToolButton>
      )}

      <ShortcutsHelpButton />
    </div>
  );
}

function ShortcutsHelpButton() {
  const [open, setOpen] = useState(false);
  const t = useTranslations("planner");

  return (
    <>
      <ToolButton onClick={() => setOpen(true)} tooltip={t("keyboardShortcuts")}>
        <HelpCircle size={16} />
      </ToolButton>

      {open && (
        <div className="absolute left-12 top-0 z-[1001] w-56 max-h-[70vh] overflow-y-auto bg-bg-secondary/95 backdrop-blur-sm border border-border-default rounded-lg p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-mono font-semibold text-text-primary">{t("keyboardShortcuts")}</span>
            <button onClick={() => setOpen(false)} className="text-text-tertiary hover:text-text-primary cursor-pointer">
              <X size={12} />
            </button>
          </div>
          <div className="flex flex-col gap-1">
            {PLANNER_SHORTCUTS
              // Desktop-only chords (e.g. New plan) are native in the browser, so
              // only advertise them where the dispatcher actually handles them.
              .filter((s) => !s.desktopOnly || isElectron())
              .map((s, i) => (
                <div key={`${s.key}-${i}`} className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-mono text-text-secondary truncate">{t(s.labelKey)}</span>
                  <kbd className="text-[9px] font-mono px-1 py-0.5 bg-bg-tertiary border border-border-default text-text-tertiary rounded shrink-0">{formatShortcutKey(s)}</kbd>
                </div>
              ))}
            {/* Mouse-modifier selection gestures — not keyboard shortcuts, but
                documented here since this is the only place they surface. */}
            {([["Ctrl+Click", "shortcuts.multiSelect"], ["Shift+Click", "shortcuts.rangeSelect"]] as const).map(([key, labelKey]) => (
              <div key={key} className="flex items-center justify-between gap-2">
                <span className="text-[10px] font-mono text-text-secondary truncate">{t(labelKey)}</span>
                <kbd className="text-[9px] font-mono px-1 py-0.5 bg-bg-tertiary border border-border-default text-text-tertiary rounded shrink-0">{key}</kbd>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
