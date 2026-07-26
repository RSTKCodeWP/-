/**
 * @module PlanLibraryHeader
 * @description Header bar for the flight plan library: title, new folder, new plan, collapse.
 * Owns the inline new-folder creation input (self-contained via the library store).
 * @license GPL-3.0-only
 */
"use client";

import { useState, useRef, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Plus, FolderPlus, ChevronLeft } from "lucide-react";
import { usePlanLibraryStore } from "@/stores/plan-library-store";

interface PlanLibraryHeaderProps {
  onNew: () => void;
  onCollapse: () => void;
}

export function PlanLibraryHeader({ onNew, onCollapse }: PlanLibraryHeaderProps) {
  const t = useTranslations("library");
  const createFolder = usePlanLibraryStore((s) => s.createFolder);
  const toggleFolder = usePlanLibraryStore((s) => s.toggleFolder);

  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const startCreate = useCallback(() => {
    setName("");
    setCreating(true);
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  const confirmCreate = useCallback(() => {
    const trimmed = name.trim();
    if (trimmed) {
      const id = createFolder(trimmed);
      // Expand the freshly-created folder so it is visible immediately.
      toggleFolder(id);
    }
    setCreating(false);
    setName("");
  }, [name, createFolder, toggleFolder]);

  const cancelCreate = useCallback(() => {
    setCreating(false);
    setName("");
  }, []);

  return (
    <div className="flex items-center justify-between px-3 py-2 border-b border-border-default">
      {creating ? (
        <input
          ref={inputRef}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") confirmCreate();
            if (e.key === "Escape") cancelCreate();
          }}
          onBlur={confirmCreate}
          placeholder={t("folderName")}
          className="flex-1 min-w-0 mr-2 px-2 py-0.5 text-xs bg-bg-tertiary border border-border-default text-text-primary outline-none"
        />
      ) : (
        <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
          {t("title")}
        </span>
      )}
      <div className="flex items-center gap-1 shrink-0">
        <button
          onClick={startCreate}
          className="p-1 text-text-tertiary hover:text-text-primary transition-colors cursor-pointer"
          title={t("newFolder")}
        >
          <FolderPlus size={14} />
        </button>
        <button
          onClick={onNew}
          className="p-1 text-text-tertiary hover:text-text-primary transition-colors cursor-pointer"
          title={t("newPlan")}
        >
          <Plus size={14} />
        </button>
        <button
          onClick={onCollapse}
          className="p-1 text-text-tertiary hover:text-text-primary transition-colors cursor-pointer"
          title={t("collapsePanel")}
        >
          <ChevronLeft size={14} />
        </button>
      </div>
    </div>
  );
}
