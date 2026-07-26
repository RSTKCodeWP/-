"use client";

/**
 * @module node-detail/agent/NodeSubNav
 * @description Reusable secondary-sidebar chrome for a node-detail page that
 * hosts sub-pages (the Agent page). A titled left rail with labelled sections
 * and nav-item buttons; the active item gets the accent tint + left border.
 * Styled to match the Setup tab's Flight Controller sidebar so both read as one
 * pattern.
 * @license GPL-3.0-only
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface SubNavItem {
  id: string;
  label: string;
  icon: ReactNode;
}

export interface SubNavSection {
  key: string;
  label: string;
  items: SubNavItem[];
}

interface NodeSubNavProps {
  title: string;
  sections: SubNavSection[];
  activeId: string;
  onSelect: (id: string) => void;
}

export function NodeSubNav({
  title,
  sections,
  activeId,
  onSelect,
}: NodeSubNavProps) {
  return (
    <nav className="w-[200px] border-r border-border-default bg-bg-secondary flex-shrink-0 overflow-y-auto">
      <div className="px-3 py-3 border-b border-border-default">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
          {title}
        </h2>
      </div>
      <div className="flex flex-col py-1">
        {sections.map((section) => (
          <div key={section.key}>
            <div className="px-3 pt-3 pb-1">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                {section.label}
              </span>
            </div>
            {section.items.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelect(item.id)}
                aria-current={activeId === item.id ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 px-3 py-1.5 text-xs text-left transition-colors cursor-pointer w-full",
                  activeId === item.id
                    ? "text-accent-primary bg-accent-primary/10 border-l-2 border-l-accent-primary"
                    : "text-text-secondary hover:text-text-primary hover:bg-bg-tertiary border-l-2 border-l-transparent",
                )}
              >
                {item.icon}
                {item.label}
              </button>
            ))}
          </div>
        ))}
      </div>
    </nav>
  );
}
