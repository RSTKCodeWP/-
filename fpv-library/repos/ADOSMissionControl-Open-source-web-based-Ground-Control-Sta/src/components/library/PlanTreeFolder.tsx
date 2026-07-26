/**
 * @module PlanTreeFolder
 * @description Expandable folder node in the plan tree.
 * @license GPL-3.0-only
 */
"use client";

import type { ReactNode } from "react";
import { ChevronDown, ChevronRight, Folder } from "lucide-react";
import type { PlanFolder } from "@/lib/types";

interface PlanTreeFolderProps {
  folder: PlanFolder;
  expanded: boolean;
  onToggle: () => void;
  count: number;
  children: ReactNode;
}

export function PlanTreeFolder({ folder, expanded, onToggle, count, children }: PlanTreeFolderProps) {
  return (
    <div>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-2 py-1.5 text-left hover:bg-bg-tertiary transition-colors cursor-pointer"
      >
        {expanded ? (
          <ChevronDown size={10} className="text-text-tertiary shrink-0" />
        ) : (
          <ChevronRight size={10} className="text-text-tertiary shrink-0" />
        )}
        <Folder size={12} className="text-text-secondary shrink-0" />
        <span className="text-xs font-medium text-text-primary flex-1 truncate">
          {folder.name}
        </span>
        <span className="text-[10px] font-mono text-text-tertiary">
          {count}
        </span>
      </button>
      {expanded && <div className="ml-4">{children}</div>}
    </div>
  );
}
