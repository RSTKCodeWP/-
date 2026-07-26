/**
 * @module use-skill-input
 * @description The global cockpit input dispatcher. One window keydown
 * listener plus a gamepad button edge-detector resolve the active loadout's
 * bindings to a Skill and activate it through the registry's single gating
 * pipeline (text-field guard, arm-requirement, confirm, idempotency).
 *
 * Keyboard and gamepad are two sources into the same resolve-and-activate
 * path; a binding only ever names a Skill id, so it can never bypass a
 * safety gate. Bound gamepad buttons stay in the MANUAL_CONTROL bitmask —
 * the action edge is purely additive on top of the flight-control stream.
 *
 * Replaces the per-action Shift+key listener: the default loadout reproduces
 * the exact Shift+A/T/L/P/R/X chords for muscle-memory parity.
 *
 * @license GPL-3.0-only
 */

import { useEffect, useRef } from "react";
import { useToast } from "@/components/ui/toast";
import { useSettingsStore } from "@/stores/settings-store";
import { useInputStore } from "@/stores/input-store";
import { useDroneManager } from "@/stores/drone-manager";
import { activate, buildSkillContext } from "@/lib/skills";
import { canonicalChord } from "@/lib/skills/chord";
import type { SkillActivateArgs, SkillContext } from "@/lib/skills/types";

interface UseSkillInputOptions {
  /** When false the dispatcher is dormant (e.g. while a modal owns input). */
  enabled: boolean;
}

/** True when the event originates from an editable field — never dispatch. */
function isTextTarget(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement ||
    (target instanceof HTMLElement && target.isContentEditable)
  );
}

/**
 * Build the activation args for a Skill. Mode-preset skills bake their own
 * target, so the dispatcher passes no targetMode; takeoff altitude defaults
 * are resolved inside the built-in. Returns undefined when there is nothing
 * to add (the registry applies its own defaults).
 */
function activateArgsFor(_skillId: string): SkillActivateArgs | undefined {
  return undefined;
}

export function useSkillInput({ enabled }: UseSkillInputOptions): void {
  const { toast } = useToast();

  // Keep the live toast in a ref so the long-lived listeners always reach
  // the current notifier without re-subscribing on every render.
  const toastRef = useRef(toast);
  toastRef.current = toast;

  // Resolve the active loadout slots fresh at dispatch time so a rebind takes
  // effect without re-registering the listener.
  function dispatchSkill(skillId: string): void {
    const droneId = useDroneManager.getState().selectedDroneId;
    if (!droneId) return;
    const ctx: SkillContext = buildSkillContext(droneId);
    // Inject the live toast as the user-facing notifier.
    ctx.notify = (message: string, status?: "success" | "warning" | "error" | "info") =>
      toastRef.current(message, status);
    void activate(skillId, ctx, activateArgsFor(skillId));
  }

  // Keyboard half: one window keydown listener.
  useEffect(() => {
    if (!enabled) return;

    function handleKey(e: KeyboardEvent): void {
      if (isTextTarget(e.target)) return;

      const chord = canonicalChord(e);
      if (!chord) return;

      const { loadouts, activeLoadoutId } = useSettingsStore.getState();
      const loadout = loadouts[activeLoadoutId];
      if (!loadout) return;

      const slot = loadout.slots.find(
        (s) => s.key === chord && s.skillId !== null,
      );
      if (!slot || slot.skillId === null) return;

      e.preventDefault();
      dispatchSkill(slot.skillId);
    }

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
    // dispatchSkill closes over stable store getters + a ref'd toast; it does
    // not need to be a dependency.
  }, [enabled]);

  // Gamepad half: edge-detect false->true transitions on input-store buttons.
  useEffect(() => {
    if (!enabled) return;

    // Seed from the current state so a button already held at mount does not
    // register a spurious edge.
    const prevButtons: boolean[] = [...useInputStore.getState().buttons];

    const unsubscribe = useInputStore.subscribe((state) => {
      const buttons = state.buttons;
      const { loadouts, activeLoadoutId } = useSettingsStore.getState();
      const loadout = loadouts[activeLoadoutId];

      for (let i = 0; i < buttons.length; i++) {
        const wasDown = prevButtons[i] ?? false;
        const isDown = buttons[i] ?? false;
        // Off->on edge only: holding a bound button never re-fires the skill,
        // while the bitmask keeps reporting the held state to the FC.
        if (isDown && !wasDown && loadout) {
          const slot = loadout.slots.find(
            (s) => s.gamepadButton === i && s.skillId !== null,
          );
          if (slot && slot.skillId !== null) {
            dispatchSkill(slot.skillId);
          }
        }
        prevButtons[i] = isDown;
      }
    });

    return () => unsubscribe();
  }, [enabled]);
}
