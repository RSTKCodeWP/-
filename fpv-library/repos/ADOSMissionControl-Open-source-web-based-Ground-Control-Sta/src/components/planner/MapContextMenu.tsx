/**
 * @module MapContextMenu
 * @description Floating right-click context menu for the planner map.
 * Renders at absolute screen coordinates and auto-closes on outside click or Escape.
 * @license GPL-3.0-only
 */
"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

export interface ContextMenuItem {
  id: string;
  label: string;
  danger?: boolean;
  divider?: boolean;
}

interface MapContextMenuProps {
  x: number;
  y: number;
  items: ContextMenuItem[];
  onSelect: (id: string) => void;
  onClose: () => void;
}

export function MapContextMenu({ x, y, items, onSelect, onClose }: MapContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const escHandler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", handler);
    document.addEventListener("keydown", escHandler);
    return () => {
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("keydown", escHandler);
    };
  }, [onClose]);

  return (
    <div
      ref={ref}
      className="fixed z-[2000] min-w-[160px] bg-bg-secondary border border-border-default py-1 shadow-lg"
      style={{ left: x, top: y }}
    >
      {items.map((item) =>
        item.divider ? (
          <div key={item.id} className="h-px bg-border-default my-1" />
        ) : (
          <button
            key={item.id}
            className={cn(
              "w-full flex items-center px-3 py-1.5 text-xs text-left transition-colors cursor-pointer",
              item.danger
                ? "text-status-error hover:bg-status-error/10"
                : "text-text-primary hover:bg-bg-tertiary"
            )}
            onClick={() => {
              onSelect(item.id);
              onClose();
            }}
          >
            {item.label}
          </button>
        )
      )}
    </div>
  );
}
