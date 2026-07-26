/**
 * @module components/mcp/watch/McpAutoNavBridge
 * @description The "watch it work" follow layer. When Follow-Lock is on, each
 * new MCP tool call auto-navigates the GCS to the surface it touched, flashes
 * the triggering feed row, and pulses the viewport, so operating a drone through
 * an AI feels like watching the model assemble itself. Anti-disorientation uses
 * an opt-in follow model: a persistent accent border + a "Following MCP" banner
 * explain every move, any
 * manual interaction (outside the rail) drops follow, and bursts are debounced
 * to one jump. Renders the follow indicator; logic runs in effects. Mounted
 * once, shell-wide, in CommandShell.
 * @license GPL-3.0-only
 */

"use client";

import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { useMcpActivityStore } from "@/stores/mcp-activity-store";
import { useMcpFollowStore } from "@/stores/mcp-follow-store";
import { useUiStore } from "@/stores/ui-store";
import { navigateToRow, nodeDisplayName } from "@/lib/mcp/navigate";
import type { McpActivityRow } from "@/lib/mcp/activity";

const DEBOUNCE_MS = 400;
const FLASH_MS = 1400;
/** Ignore drop-on-interact this long after enabling, so the enabling click
 *  (and its trailing pointerup) does not immediately drop follow. */
const GRACE_MS = 500;

function routeLabel(path: string): string {
  if (path === "/plan") return "Mission";
  if (path === "/mcp") return "MCP";
  return path.replace(/^\//, "") || "GCS";
}

export function McpAutoNavBridge() {
  const t = useTranslations("mcp");
  const latestNav = useMcpActivityStore((s) => s.latestNav);
  const followLock = useMcpFollowStore((s) => s.followLock);
  const followingNode = useMcpFollowStore((s) => s.followingNode);
  const arrivedAt = useMcpFollowStore((s) => s.arrivedAt);
  const setFollowLock = useMcpFollowStore((s) => s.setFollowLock);

  const mountedAtRef = useRef(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Stamp mount time in an effect (Date.now is impure — not called in render) so
  // a persisted Follow-Lock never auto-navigates on the backlog burst at load.
  useEffect(() => {
    mountedAtRef.current = Date.now();
  }, []);

  // Auto-navigate to the latest terminal event while following. Backlog events
  // (older than mount) never trigger a jump, so a persisted Follow-Lock does not
  // teleport on load. Bursts debounce to a single jump to the newest target.
  useEffect(() => {
    if (!followLock || !latestNav) return;
    if (latestNav.tsUs / 1000 < mountedAtRef.current) return; // backlog

    const row: McpActivityRow = latestNav;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const result = navigateToRow(row);
      if (result === null) return; // feed-only row, nothing to follow to
      const label =
        result === "routed"
          ? row.surface?.kind === "route"
            ? routeLabel(row.surface.path)
            : "GCS"
          : nodeDisplayName(row.node);
      useMcpFollowStore.getState().arrive(label, row.id);
      if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
      flashTimerRef.current = setTimeout(() => useMcpFollowStore.getState().clearFlash(), FLASH_MS);
    }, DEBOUNCE_MS);
  }, [followLock, latestNav]);

  // Enabling Follow-Lock opens the MCP panel so the operator can watch along.
  useEffect(() => {
    if (followLock) useUiStore.getState().setRightRailPanel("mcp");
  }, [followLock]);

  // Any manual interaction outside the rail drops follow. A short
  // grace after enabling ignores the enabling click; interacting with the rail
  // itself (scrolling the feed, toggling) never drops follow.
  useEffect(() => {
    if (!followLock) return;
    const enabledAt = Date.now();
    const drop = (e: Event) => {
      if (Date.now() - enabledAt < GRACE_MS) return;
      const target = e.target as HTMLElement | null;
      if (target?.closest("[data-mcp-rail]")) return;
      setFollowLock(false);
    };
    window.addEventListener("pointerdown", drop, true);
    window.addEventListener("wheel", drop, { capture: true, passive: true });
    window.addEventListener("keydown", drop, true);
    return () => {
      window.removeEventListener("pointerdown", drop, true);
      window.removeEventListener("wheel", drop, true);
      window.removeEventListener("keydown", drop, true);
    };
  }, [followLock, setFollowLock]);

  useEffect(
    () => () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
    },
    [],
  );

  if (!followLock) return null;

  return (
    <>
      {/* Colored viewport border — the persistent "why the view moved" cue. */}
      <div
        className="pointer-events-none fixed inset-0 z-40 border-2 border-accent-primary/70"
        aria-hidden="true"
      />
      {/* Arrival pulse — re-mounts on each jump (keyed by the arrival marker). */}
      {arrivedAt > 0 && (
        <span
          key={arrivedAt}
          className="ados-mcp-arrive pointer-events-none fixed inset-0 z-40"
          aria-hidden="true"
        />
      )}
      {/* Following banner. */}
      <div
        role="status"
        className="fixed left-1/2 top-14 z-50 flex -translate-x-1/2 items-center gap-2 rounded-full border border-accent-primary/60 bg-bg-secondary/95 px-3 py-1 shadow-lg backdrop-blur"
      >
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-2 w-2 animate-ping rounded-full bg-accent-primary opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-accent-primary" />
        </span>
        <span className="text-xs text-text-secondary">
          {t("watch.following", { node: followingNode ?? "…" })}
        </span>
        <button
          type="button"
          onClick={() => setFollowLock(false)}
          className="text-xs font-medium text-accent-primary hover:underline"
        >
          {t("watch.stopFollow")}
        </button>
      </div>
    </>
  );
}
