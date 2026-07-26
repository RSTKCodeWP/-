/**
 * @module PlanTree
 * @description Renders the plan library as a list with folder grouping.
 * Owns the folder context menu (rename / delete).
 * @license GPL-3.0-only
 */
"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import type { SavedPlan, PlanFolder } from "@/lib/types";
import { usePlanLibraryStore } from "@/stores/plan-library-store";
import { useToast } from "@/components/ui/toast";
import { PlanTreeFolder } from "./PlanTreeFolder";
import { PlanTreeItem } from "./PlanTreeItem";

interface PlanTreeProps {
  plans: SavedPlan[];
  folders: PlanFolder[];
  activePlanId: string | null;
  isDirty: boolean;
  expandedFolders: string[];
  context: "plan" | "simulate";
  onSelect: (planId: string) => void;
  /** Save handler for inline save button on active+dirty items. */
  onSave?: () => void;
  /** Called when a plan is renamed via context menu (syncs planner state for active plan). */
  onPlanRenamed?: (name: string) => void;
}

export function PlanTree({
  plans,
  folders,
  activePlanId,
  isDirty,
  expandedFolders,
  context,
  onSelect,
  onSave,
  onPlanRenamed,
}: PlanTreeProps) {
  const t = useTranslations("library");
  const { toast } = useToast();
  const toggleFolder = usePlanLibraryStore((s) => s.toggleFolder);
  const renameFolder = usePlanLibraryStore((s) => s.renameFolder);
  const deleteFolder = usePlanLibraryStore((s) => s.deleteFolder);

  const [folderMenu, setFolderMenu] = useState<{ id: string; x: number; y: number } | null>(null);
  const [renamingFolder, setRenamingFolder] = useState(false);
  const [folderRenameValue, setFolderRenameValue] = useState("");
  const folderMenuRef = useRef<HTMLDivElement>(null);
  const folderRenameRef = useRef<HTMLInputElement>(null);

  const closeFolderMenu = useCallback(() => {
    setFolderMenu(null);
    setRenamingFolder(false);
  }, []);

  const openFolderMenu = useCallback((e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    setRenamingFolder(false);
    setFolderMenu({ id, x: e.clientX, y: e.clientY });
  }, []);

  const openFolderMenuAt = useCallback((rect: DOMRect, id: string) => {
    setRenamingFolder(false);
    setFolderMenu({ id, x: rect.right, y: rect.bottom });
  }, []);

  useEffect(() => {
    if (!folderMenu) return;
    const handler = (e: MouseEvent) => {
      if (folderMenuRef.current && !folderMenuRef.current.contains(e.target as Node)) {
        closeFolderMenu();
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [folderMenu, closeFolderMenu]);

  useEffect(() => {
    if (renamingFolder && folderRenameRef.current) {
      folderRenameRef.current.focus();
      folderRenameRef.current.select();
    }
  }, [renamingFolder]);

  const startFolderRename = useCallback(() => {
    const folder = folders.find((f) => f.id === folderMenu?.id);
    if (!folder) return;
    setFolderRenameValue(folder.name);
    setRenamingFolder(true);
  }, [folders, folderMenu]);

  const confirmFolderRename = useCallback(() => {
    if (folderMenu && folderRenameValue.trim()) {
      renameFolder(folderMenu.id, folderRenameValue.trim());
      toast(t("folderRenamed"), "info");
    }
    closeFolderMenu();
  }, [folderMenu, folderRenameValue, renameFolder, toast, t, closeFolderMenu]);

  const handleFolderDelete = useCallback(() => {
    if (folderMenu) {
      deleteFolder(folderMenu.id);
      toast(t("folderDeleted"), "info");
    }
    closeFolderMenu();
  }, [folderMenu, deleteFolder, toast, t, closeFolderMenu]);

  // Separate folder plans from root plans
  const folderMap = new Map<string, SavedPlan[]>();
  const rootPlans: SavedPlan[] = [];

  for (const plan of plans) {
    if (plan.folderId) {
      const arr = folderMap.get(plan.folderId) || [];
      arr.push(plan);
      folderMap.set(plan.folderId, arr);
    } else {
      rootPlans.push(plan);
    }
  }

  const sortedFolders = [...folders].sort((a, b) => a.order - b.order);

  return (
    <div className="p-2 flex flex-col gap-0.5">
      {sortedFolders.map((folder) => {
        const folderPlans = folderMap.get(folder.id) || [];
        return (
          <div
            key={folder.id}
            className="group relative"
            onContextMenu={(e) => openFolderMenu(e, folder.id)}
          >
            <PlanTreeFolder
              folder={folder}
              expanded={expandedFolders.includes(folder.id)}
              onToggle={() => toggleFolder(folder.id)}
              count={folderPlans.length}
            >
              {folderPlans.map((plan) => (
                <PlanTreeItem
                  key={plan.id}
                  plan={plan}
                  isActive={plan.id === activePlanId}
                  isDirty={plan.id === activePlanId && isDirty}
                  context={context}
                  onSelect={() => onSelect(plan.id)}
                  onSave={plan.id === activePlanId ? onSave : undefined}
                  onPlanRenamed={plan.id === activePlanId ? onPlanRenamed : undefined}
                />
              ))}
            </PlanTreeFolder>
            <span
              role="button"
              title={t("moreActions")}
              onClick={(e) => {
                e.stopPropagation();
                openFolderMenuAt(e.currentTarget.getBoundingClientRect(), folder.id);
              }}
              className="absolute right-6 top-[9px] p-0.5 text-text-tertiary hover:text-text-primary opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer z-10"
            >
              <MoreHorizontal size={12} />
            </span>
          </div>
        );
      })}

      {rootPlans.map((plan) => (
        <PlanTreeItem
          key={plan.id}
          plan={plan}
          isActive={plan.id === activePlanId}
          isDirty={plan.id === activePlanId && isDirty}
          context={context}
          onSelect={() => onSelect(plan.id)}
          onSave={plan.id === activePlanId ? onSave : undefined}
          onPlanRenamed={plan.id === activePlanId ? onPlanRenamed : undefined}
        />
      ))}

      {folderMenu && (
        <div
          ref={folderMenuRef}
          className="fixed z-[2000] bg-bg-primary border border-border-default shadow-lg py-1 min-w-[160px]"
          style={{ left: folderMenu.x, top: folderMenu.y }}
        >
          {renamingFolder ? (
            <div className="px-2 py-1">
              <input
                ref={folderRenameRef}
                value={folderRenameValue}
                onChange={(e) => setFolderRenameValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") confirmFolderRename();
                  if (e.key === "Escape") closeFolderMenu();
                }}
                onBlur={confirmFolderRename}
                placeholder={t("folderName")}
                className="w-full px-2 py-1 text-xs bg-bg-tertiary border border-border-default text-text-primary outline-none"
              />
            </div>
          ) : (
            <>
              <button
                onClick={startFolderRename}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-left text-text-primary hover:bg-bg-tertiary transition-colors cursor-pointer"
              >
                <Pencil size={12} />
                {t("rename")}
              </button>
              <div className="my-1 border-t border-border-default" />
              <button
                onClick={handleFolderDelete}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-left text-status-error hover:bg-status-error/10 transition-colors cursor-pointer"
              >
                <Trash2 size={12} />
                {t("delete")}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
