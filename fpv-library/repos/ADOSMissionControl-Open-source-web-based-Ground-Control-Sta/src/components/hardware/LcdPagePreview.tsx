"use client";

/**
 * @module LcdPagePreview
 * @description Shows a 240x160 thumbnail of whatever the agent's local
 * LCD is rendering right now. Polls the snapshot URL at 1 Hz, cache-busts
 * on every poll, and falls back to a placeholder when the agent has not
 * shipped a snapshot endpoint or the request 404s. Lazy-loads the image
 * once the card scrolls into view so off-screen instances do not burn
 * heartbeats.
 * @license GPL-3.0-only
 */

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Monitor, Loader2, ImageOff } from "lucide-react";
import { useAgentCapabilitiesStore } from "@/stores/agent-capabilities-store";
import { useAgentConnectionStore } from "@/stores/agent-connection-store";

const POLL_INTERVAL_MS = 1000;
const PREVIEW_W = 240;
const PREVIEW_H = 160;

export function LcdPagePreview() {
  const display = useAgentCapabilitiesStore((s) => s.display);
  const loaded = useAgentCapabilitiesStore((s) => s.loaded);
  const agentUrl = useAgentConnectionStore((s) => s.agentUrl);
  const t = useTranslations("hardware.lcdPagePreview");

  const containerRef = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);
  const [src, setSrc] = useState<string | null>(null);
  const [errored, setErrored] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Lazy mount: only start polling once the card scrolls into view.
  // Falls back to immediate visibility when IntersectionObserver is
  // missing (older browsers, some test environments).
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined" || !containerRef.current) {
      setVisible(true);
      return;
    }
    const el = containerRef.current;
    const obs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setVisible(true);
            obs.disconnect();
            return;
          }
        }
      },
      { rootMargin: "100px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // 1 Hz polling. The src is recomputed on every tick so the browser
  // refetches the framebuffer thumbnail. Pauses while the tab is
  // hidden and tears down on unmount.
  useEffect(() => {
    if (!visible || !loaded) return;
    if (!display || !display.hasTouch && !display.snapshotUrl) {
      // Still tick the UI so the placeholder updates if the URL
      // appears mid-session.
    }
    const url = display?.snapshotUrl ?? null;
    if (!url) {
      setSrc(null);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const tick = () => {
      if (cancelled) return;
      if (typeof document !== "undefined" && document.hidden) return;
      const cacheBust = `${url}${url.includes("?") ? "&" : "?"}t=${Date.now()}`;
      // Re-arm the image before each poll. onError unmounts the <img> (the
      // render gate is `src && !errored`), and onLoad is the only place that
      // clears `errored` — so without resetting it here a single transient
      // 404/blip would freeze the placeholder for the rest of the session
      // even after the endpoint recovers. Clearing it lets the keyed <img>
      // remount against the fresh URL and retry every second.
      setErrored(false);
      setSrc(cacheBust);
    };

    tick();
    timer = setInterval(tick, POLL_INTERVAL_MS);

    const onVisibility = () => {
      if (typeof document !== "undefined" && !document.hidden) tick();
    };
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", onVisibility);
    }

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
      if (typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", onVisibility);
      }
    };
  }, [visible, loaded, display]);

  // Don't render if the agent has no display bound. The Hardware
  // page already hides the parent wrapper in that case, but this
  // keeps the component a no-op when used elsewhere.
  if (!loaded || !display || display.type === "none") {
    return null;
  }

  const hostname = (() => {
    if (!agentUrl) return "agent";
    try {
      const u = new URL(agentUrl);
      return u.hostname.replace(/\.local$/, "");
    } catch {
      return "agent";
    }
  })();
  const activePage = display.activePage ?? "-";

  return (
    <section
      ref={containerRef}
      className="rounded border border-border-default bg-bg-secondary"
    >
      <header className="flex items-center justify-between border-b border-border-default px-4 py-3">
        <div className="flex items-center gap-2">
          <Monitor size={16} className="text-accent-primary" />
          <h2 className="text-sm font-display font-semibold text-text-primary">
            {t("title")}
          </h2>
        </div>
        {refreshing ? (
          <Loader2
            size={12}
            className="animate-spin text-text-tertiary"
            aria-label={t("refresh")}
            role="status"
          />
        ) : null}
      </header>
      <div className="flex flex-col items-center gap-2 px-4 py-4">
        <div
          className="flex items-center justify-center overflow-hidden rounded border border-border-default bg-bg-tertiary"
          style={{ width: PREVIEW_W, height: PREVIEW_H }}
        >
          {src && !errored ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={src}
              src={src}
              alt={t("title")}
              width={PREVIEW_W}
              height={PREVIEW_H}
              className="h-full w-full object-contain"
              loading="lazy"
              onLoadStart={() => setRefreshing(true)}
              onLoad={() => {
                setRefreshing(false);
                setErrored(false);
              }}
              onError={() => {
                setRefreshing(false);
                setErrored(true);
              }}
            />
          ) : (
            <div className="flex flex-col items-center gap-1 text-text-tertiary">
              <ImageOff size={20} />
              <span className="text-[10px] uppercase tracking-wide">
                {t("noSnapshot")}
              </span>
            </div>
          )}
        </div>
        <p className="font-mono text-xs text-text-secondary">
          {t("captionDevice", { host: hostname, page: activePage })}
        </p>
      </div>
    </section>
  );
}
