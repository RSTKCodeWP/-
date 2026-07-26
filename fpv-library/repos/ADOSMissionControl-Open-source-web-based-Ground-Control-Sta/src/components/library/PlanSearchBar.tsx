/**
 * @module PlanSearchBar
 * @description Search input and sort toggle for the plan library.
 * Listens for `plan-library:focus-search` custom event (dispatched by Cmd+O).
 * @license GPL-3.0-only
 */
"use client";

import { useRef, useEffect } from "react";
import { Search, ArrowUpDown } from "lucide-react";
import { usePlanLibraryStore } from "@/stores/plan-library-store";

const SORT_LABELS: Record<string, string> = { date: "Date", name: "Name", waypoints: "WPs" };

export function PlanSearchBar() {
  const inputRef = useRef<HTMLInputElement>(null);
  const searchQuery = usePlanLibraryStore((s) => s.searchQuery);
  const setSearchQuery = usePlanLibraryStore((s) => s.setSearchQuery);
  const sortBy = usePlanLibraryStore((s) => s.sortBy);
  const setSortBy = usePlanLibraryStore((s) => s.setSortBy);

  // Listen for Cmd+O focus event
  useEffect(() => {
    const handler = () => {
      inputRef.current?.focus();
      inputRef.current?.select();
    };
    document.addEventListener("plan-library:focus-search", handler);
    return () => document.removeEventListener("plan-library:focus-search", handler);
  }, []);

  // Click cycles sort field only (direction auto-flips when wrapping back)
  const cycleSortBy = () => {
    const order: ("date" | "name" | "waypoints")[] = ["date", "name", "waypoints"];
    const idx = order.indexOf(sortBy);
    const next = order[(idx + 1) % order.length];
    setSortBy(next);
  };

  return (
    <div className="px-3 py-2 border-b border-border-default flex items-center gap-2">
      <div className="flex-1 flex items-center gap-2 px-2 py-1 bg-bg-primary border border-border-default">
        <Search size={12} className="text-text-tertiary shrink-0" />
        <input
          ref={inputRef}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search plans..."
          className="flex-1 bg-transparent text-xs text-text-primary placeholder:text-text-tertiary outline-none"
        />
      </div>
      <button
        onClick={cycleSortBy}
        className="flex items-center gap-1 p-1 text-text-tertiary hover:text-text-primary transition-colors cursor-pointer"
        title={`Sort by ${sortBy}`}
      >
        <ArrowUpDown size={12} />
        <span className="text-[10px] font-mono">{SORT_LABELS[sortBy]}</span>
      </button>
    </div>
  );
}
