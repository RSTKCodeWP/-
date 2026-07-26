/**
 * @module map/context-menu/MenuItem
 * @description Single row inside the right-click flight map menu.
 * Renders an SVG icon, the label, and an optional shortcut hint.
 * @license GPL-3.0-only
 */

"use client";

import { ICONS } from "../map-context-menu-icons";
import type { MenuItemDef } from "./types";

interface MenuItemProps {
  item: MenuItemDef;
  highlighted: boolean;
  onClick: () => void;
  onMouseEnter: () => void;
}

export function MenuItem({ item, highlighted, onClick, onMouseEnter }: MenuItemProps) {
  return (
    <button
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      className={`w-full text-left px-3 py-1.5 text-[11px] font-mono transition-colors flex items-center gap-2.5 cursor-pointer ${
        highlighted
          ? "bg-bg-tertiary text-text-primary"
          : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
      } ${item.danger ? "text-status-error" : ""}`}
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 14 14"
        fill="none"
        className="shrink-0"
        dangerouslySetInnerHTML={{ __html: ICONS[item.icon] || "" }}
      />
      <span className="flex-1">{item.label}</span>
      {item.shortcut && <span className="text-[9px] text-text-tertiary">{item.shortcut}</span>}
    </button>
  );
}
