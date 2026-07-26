"use client";

/**
 * @module use-target-action-hotkeys
 * @description Fires a TARGET-ACTION by its hotkey on the currently-SELECTED
 * target. While the operator has a detection selected in the cockpit overlay,
 * pressing an action's key (e.g. "d" for Designate) runs that action on the
 * selection — so a target action can be triggered by a hotkey, not only the
 * click popup. Inert when nothing is selected.
 *
 * The listener runs in the capture phase and stops propagation when it handles
 * a key, so a target action preempts a Skill Bar binding on the same key while a
 * target is selected (and yields to the Skill Bar the moment nothing is).
 *
 * @license GPL-3.0-only
 */

import { useEffect } from "react";

import { useToast } from "@/components/ui/toast";
import { resolveTargetActions } from "@/lib/skills/target-actions";
import { useSelectedTargetStore } from "@/stores/selected-target-store";

function isTextField(el: EventTarget | null): boolean {
  return (
    el instanceof HTMLInputElement ||
    el instanceof HTMLTextAreaElement ||
    el instanceof HTMLSelectElement ||
    (el instanceof HTMLElement && el.isContentEditable)
  );
}

export function useTargetActionHotkeys({
  enabled = true,
}: { enabled?: boolean } = {}) {
  const { toast } = useToast();

  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.repeat) return;
      if (isTextField(e.target)) return;
      const target = useSelectedTargetStore.getState().selected;
      if (!target) return;
      const key = e.key.toLowerCase();
      const action = resolveTargetActions(target).find(
        (a) => a.defaultKey && a.defaultKey.toLowerCase() === key,
      );
      if (!action) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      void Promise.resolve(
        action.activate({
          target,
          notify: (message, status) => toast(message, status ?? "info"),
        }),
      ).finally(() => useSelectedTargetStore.getState().clear());
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [enabled, toast]);
}
