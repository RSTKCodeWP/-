import { useState } from "react";

import { ConsoleRail } from "./components/ConsoleRail";
import { DemoBanner } from "./components/DemoBanner";
import { StatusStrip } from "./components/StatusStrip";
import { useFileMission } from "./data/fileMission";
import { DocsPanel } from "./docs/DocsPanel";
import { useMockMission } from "./mock/useMockMission";
import { MapPage } from "./pages/MapPage";
import { OpsPage } from "./pages/OpsPage";
import { ReviewPage } from "./pages/ReviewPage";
import { SettingsPage } from "./pages/SettingsPage";
import { useNavStore } from "./store/nav";
import { useClock } from "./ui/useClock";
import { useRealService } from "./ws/useRealService";

/* The coordinator UI shell — now a small INSTRUMENT CONSOLE (UI overhaul §11): a persistent
 * status strip + mode-switcher rail frame four modes (OPS / REVIEW / MAP / SET) over the SAME
 * global stores. The map is still the application (OPS + MAP); the rail never demotes it to a
 * tab. The SAME UI runs against three interchangeable sources (only the source swaps, every
 * store/region/mode is reused):
 *  - the static demo site (`--mode web`, Phase 6) → a baked `mission.json` via `useFileMission`,
 *  - the Electron app with the preload bridge → the real Python WS via `useRealService`,
 *  - a plain dev browser → the synthetic canned mock via `useMockMission`. */

const IS_WEB_DEMO = import.meta.env.MODE === "web";

export function App() {
  const clock = useClock();
  const mode = useNavStore((s) => s.mode);
  const [docsOpen, setDocsOpen] = useState(false);

  // Source selection (unchanged) — the web-demo build is decided at build time (`--mode web`);
  // under Electron the preload exposes real service ports → real Python WS; a plain dev browser
  // → the synthetic mock. All three feed the SAME stores. Off under VITEST.
  const realConfig = typeof window !== "undefined" ? (window.hades?.service ?? null) : null;
  useFileMission(!import.meta.env.VITEST && IS_WEB_DEMO);
  useRealService(import.meta.env.VITEST || IS_WEB_DEMO ? null : realConfig);
  useMockMission(!import.meta.env.VITEST && !IS_WEB_DEMO && realConfig === null);

  // The status strip + demo banner are ABOVE the rail and persist on EVERY mode (§11.4) — link
  // state and demo provenance are never mode-specific (a P0 concern). The DOCS toggle opens the
  // shared docs panel over the whole frame so the operator is never trapped; closing returns to
  // the current mode. (Docs also has a home in the SET mode — one source, two entry points.)
  return (
    <div className="flex h-full min-w-[1280px] flex-col bg-bg-base text-text-hi">
      <DemoBanner />
      <StatusStrip clock={clock} onOpenDocs={() => setDocsOpen(true)} />
      {docsOpen ? (
        <DocsPanel onClose={() => setDocsOpen(false)} />
      ) : (
        <div className="flex min-h-0 flex-1">
          <ConsoleRail />
          <div className="min-h-0 flex-1">
            {mode === "ops" && <OpsPage />}
            {mode === "review" && <ReviewPage />}
            {mode === "map" && <MapPage />}
            {mode === "set" && <SettingsPage onOpenDocs={() => setDocsOpen(true)} />}
          </div>
        </div>
      )}
    </div>
  );
}
