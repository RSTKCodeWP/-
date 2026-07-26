/**
 * @module PreflightChecklist
 * @description Pre-flight checklist panel for the mission planner. Renders the
 * default checklist grouped by category with a per-item toggle and a running
 * progress count. The operator ticks items off before uploading a mission.
 *
 * Checked state is local to this component (the checklist is advisory, not
 * persisted telemetry). All logic lives in the pure `preflight-checklist`
 * module; this file is presentation + local state only.
 * @license GPL-3.0-only
 */
"use client";

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { CheckSquare, Square, ClipboardCheck, CheckCircle2 } from "lucide-react";
import {
  DEFAULT_CHECKLIST,
  toggleItem,
  setAllChecked,
  checklistProgress,
  groupByCategory,
  type ChecklistItem,
  type CheckedMap,
} from "@/lib/preflight-checklist";

interface PreflightChecklistProps {
  /** Override the item set (defaults to the built-in checklist). */
  items?: readonly ChecklistItem[];
  /**
   * Optional callback fired after each toggle with whether every item is now
   * ticked. Lets a parent gate an upload button on a complete checklist.
   */
  onCompleteChange?: (complete: boolean) => void;
}

export function PreflightChecklist({
  items = DEFAULT_CHECKLIST,
  onCompleteChange,
}: PreflightChecklistProps) {
  const t = useTranslations("planner.checklist");
  const [checked, setChecked] = useState<CheckedMap>({});

  const progress = useMemo(
    () => checklistProgress(items, checked),
    [items, checked],
  );
  const groups = useMemo(() => groupByCategory(items), [items]);

  const applyState = useCallback(
    (next: CheckedMap) => {
      setChecked(next);
      onCompleteChange?.(checklistProgress(items, next).complete);
    },
    [items, onCompleteChange],
  );

  const handleToggle = useCallback(
    (id: string) => applyState(toggleItem(checked, id)),
    [applyState, checked],
  );

  const handleClear = useCallback(
    () => applyState(setAllChecked(items, false)),
    [applyState, items],
  );

  return (
    <div className="flex flex-col gap-2 bg-bg-secondary border border-border-default rounded p-3">
      {/* Header + progress */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-text-primary">
          <ClipboardCheck size={13} className="text-accent-primary" />
          <span className="text-[11px] font-mono font-semibold uppercase tracking-wide">
            {t("title")}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {progress.complete ? (
            <span className="flex items-center gap-1 text-[10px] font-mono text-status-success">
              <CheckCircle2 size={11} />
              {t("ready")}
            </span>
          ) : (
            <span className="text-[10px] font-mono text-text-secondary tabular-nums">
              {t("progress", {
                checked: progress.checked,
                total: progress.total,
              })}
            </span>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 w-full rounded bg-bg-tertiary overflow-hidden">
        <div
          className={`h-full transition-all ${
            progress.complete ? "bg-status-success" : "bg-accent-primary"
          }`}
          style={{ width: `${Math.round(progress.ratio * 100)}%` }}
        />
      </div>

      {/* Grouped items */}
      <div className="flex flex-col gap-2">
        {groups.map((group) => (
          <div key={group.category} className="flex flex-col gap-0.5">
            <span className="text-[9px] font-mono uppercase tracking-wide text-text-tertiary px-0.5">
              {t(`category.${group.category}`)}
            </span>
            {group.items.map((item) => {
              const isChecked = !!checked[item.id];
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handleToggle(item.id)}
                  aria-pressed={isChecked}
                  className="flex items-center gap-2 px-1.5 py-1 text-left rounded hover:bg-bg-tertiary transition-colors cursor-pointer"
                >
                  {isChecked ? (
                    <CheckSquare
                      size={13}
                      className="shrink-0 text-accent-primary"
                    />
                  ) : (
                    <Square size={13} className="shrink-0 text-text-tertiary" />
                  )}
                  <span
                    className={`text-[11px] font-mono ${
                      isChecked
                        ? "text-text-tertiary line-through"
                        : "text-text-secondary"
                    }`}
                  >
                    {t(item.labelKey)}
                  </span>
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* Clear */}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleClear}
          disabled={progress.checked === 0}
          className="text-[10px] font-mono text-text-secondary hover:text-text-primary disabled:opacity-40 disabled:cursor-default cursor-pointer transition-colors"
        >
          {t("clear")}
        </button>
      </div>
    </div>
  );
}
