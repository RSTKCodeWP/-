"use client";

/**
 * @module LcdThemeToggle
 * @description Two-state Dark / Light toggle for the agent's local
 * LCD theme. Reads the current value from the agent capabilities
 * store and writes via `POST /api/v1/setup/apply` with
 * `{ ui: { theme } }`. Includes a "Sync from my GCS" button that
 * pushes the desktop preference to the agent so the LCD matches the
 * operator's choice without a manual click. The button disables when
 * the two themes already match.
 *
 * @license GPL-3.0-only
 */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Sun, Moon, RefreshCw } from "lucide-react";
import { useAgentCapabilitiesStore } from "@/stores/agent-capabilities-store";
import { useAgentConnectionStore } from "@/stores/agent-connection-store";
import { useSettingsStore } from "@/stores/settings-store";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type AgentTheme = "dark" | "light";

export function LcdThemeToggle() {
  const uiTheme = useAgentCapabilitiesStore((s) => s.uiTheme);
  const display = useAgentCapabilitiesStore((s) => s.display);
  const loaded = useAgentCapabilitiesStore((s) => s.loaded);
  const client = useAgentConnectionStore((s) => s.client);
  const gcsTheme = useSettingsStore((s) => s.themeMode);
  const t = useTranslations("hardware.lcdTheme");
  const { toast } = useToast();

  const [optimistic, setOptimistic] = useState<AgentTheme | null>(null);
  const [pending, setPending] = useState(false);

  // Drop the optimistic shadow once the heartbeat reflects the new
  // theme. Doing this in render breaks React's update rules, so it
  // runs in an effect instead.
  useEffect(() => {
    if (optimistic && uiTheme === optimistic) {
      setOptimistic(null);
    }
  }, [uiTheme, optimistic]);

  if (!loaded || !display || display.type === "none") {
    return null;
  }

  const effectiveTheme: AgentTheme = optimistic ?? (uiTheme ?? "dark");
  // The desktop slice can hold "dark" / "light" / "auto"; only push a
  // concrete dark/light to the agent.
  const gcsConcrete: AgentTheme | null =
    gcsTheme === "dark" || gcsTheme === "light" ? gcsTheme : null;
  const inSync = gcsConcrete === effectiveTheme;

  const apply = async (next: AgentTheme) => {
    if (!client || pending || next === effectiveTheme) return;
    const previous = effectiveTheme;
    setOptimistic(next);
    setPending(true);
    try {
      await client.applySetup({ ui: { theme: next } });
    } catch (err) {
      setOptimistic(previous);
      const msg = err instanceof Error ? err.message : t("applyError");
      toast(msg, "error");
    } finally {
      setPending(false);
    }
  };

  const sync = async () => {
    if (!gcsConcrete || inSync) return;
    await apply(gcsConcrete);
  };

  return (
    <section className="rounded border border-border-default bg-bg-secondary">
      <header className="border-b border-border-default px-4 py-3">
        <h2 className="text-sm font-display font-semibold text-text-primary">
          {t("title")}
        </h2>
      </header>
      <div className="flex flex-col gap-3 px-4 py-4">
        <p className="text-xs text-text-secondary">{t("description")}</p>
        <div
          role="tablist"
          aria-label={t("title")}
          className="flex overflow-hidden rounded border border-border-default"
        >
          {(["dark", "light"] as const).map((mode) => {
            const active = effectiveTheme === mode;
            const Icon = mode === "dark" ? Moon : Sun;
            return (
              <button
                key={mode}
                role="tab"
                aria-selected={active}
                data-active={active}
                data-mode={mode}
                onClick={() => apply(mode)}
                disabled={!client || pending}
                className={cn(
                  "flex flex-1 items-center justify-center gap-2 px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-accent-primary/15 text-accent-primary"
                    : "bg-bg-tertiary text-text-secondary hover:text-text-primary",
                  (!client || pending) && "cursor-not-allowed opacity-60",
                )}
              >
                <Icon size={14} />
                <span>{mode === "dark" ? t("dark") : t("light")}</span>
              </button>
            );
          })}
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={sync}
          disabled={!client || pending || inSync || !gcsConcrete}
          className="self-start"
        >
          <span className="flex items-center gap-1.5">
            <RefreshCw size={12} />
            {inSync ? t("syncMatched") : t("syncFromGcs")}
          </span>
        </Button>
      </div>
    </section>
  );
}
