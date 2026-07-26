"use client";

import { useRef, useEffect, useCallback } from "react";
import { useSettingsStore } from "@/stores/settings-store";

/**
 * Hook to save and restore scroll position for FC panels.
 * Returns a ref to attach to the scrollable container element.
 * Saves scrollTop on scroll (debounced), restores on mount.
 */
export function usePanelScroll(panelId: string) {
  const ref = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Restore scroll position on mount
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const saved = useSettingsStore.getState().panelScrollPositions[panelId];
    if (saved && saved > 0) {
      requestAnimationFrame(() => {
        el.scrollTop = saved;
      });
    }
  }, [panelId]);

  // Save scroll position on scroll (debounced)
  const handleScroll = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      const el = ref.current;
      if (el) {
        useSettingsStore.getState().setPanelScrollPosition(panelId, el.scrollTop);
      }
    }, 300);
  }, [panelId]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      el.removeEventListener("scroll", handleScroll);
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [handleScroll]);

  return ref;
}
