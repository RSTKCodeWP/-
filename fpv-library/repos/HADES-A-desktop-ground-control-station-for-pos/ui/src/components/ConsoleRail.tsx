import { Crosshair, ListChecks, Map as MapIcon, Settings, type LucideIcon } from "lucide-react";

import { CONSOLE_MODES, useNavStore, type ConsoleMode } from "../store/nav";

/* The console mode-switcher rail (DESIGN-SYSTEM §11.1). A narrow vertical instrument rail —
 * NOT a CRUD admin sidebar: each item is a lucide glyph + a short MONO label, the active item
 * carries the same steel ACCENT BAR as a selected contact row (one selection language across
 * the whole console), and there's no logo/avatar/footer. The map stays primary; this never
 * meaningfully steals map width. The mode lives in a tiny global store so the selection spine
 * survives switching (§11.3). */

const MODES: Record<ConsoleMode, { label: string; title: string; Icon: LucideIcon }> = {
  ops: { label: "OPS", title: "Operations — the live instrument", Icon: Crosshair },
  review: { label: "REVIEW", title: "Mission Review — contacts, clearance, timeline", Icon: ListChecks },
  map: { label: "MAP", title: "Map / Playback — full-screen survivor map", Icon: MapIcon },
  set: { label: "SET", title: "Settings + Docs", Icon: Settings },
};

export function ConsoleRail() {
  const mode = useNavStore((s) => s.mode);
  const setMode = useNavStore((s) => s.setMode);

  return (
    <nav
      data-testid="console-rail"
      aria-label="Console modes"
      className="z-docked flex w-rail-w shrink-0 flex-col gap-1 border-r border-hairline bg-surface-1 px-2 py-3 shadow-card"
    >
      {CONSOLE_MODES.map((m) => {
        const { label, title, Icon } = MODES[m];
        const active = mode === m;
        return (
          <button
            key={m}
            type="button"
            data-testid={`nav-${m}`}
            aria-current={active ? "page" : undefined}
            title={title}
            onClick={() => setMode(m)}
            className={`group relative flex aspect-square flex-col items-center justify-center gap-1 rounded-md outline-none transition-colors duration-micro focus-visible:shadow-focus ${
              active
                ? "bg-blue-core text-text-on-accent shadow-card"
                : "text-text-lo hover:bg-surface-2 hover:text-text-mid"
            }`}
          >
            <Icon size={18} aria-hidden />
            <span className="font-ui text-[10px] font-semibold tracking-wide">{label}</span>
          </button>
        );
      })}
    </nav>
  );
}
