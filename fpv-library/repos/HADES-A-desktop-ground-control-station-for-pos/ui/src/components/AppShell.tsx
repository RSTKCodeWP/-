import type { ReactNode } from "react";

/* The OPS-mode fixed-grid layout (impl-plan Task 5.3; DESIGN-SYSTEM §7.1 / §8). The map is the
 * application (the largest region); the list rail and docked video sit to the right; the
 * mission log is a foot drawer. Fixed grid — no draggable panels (every C2 reference converges
 * on fixed; geometry-dragging is a maintenance sink). Each region is a labelled landmark so the
 * shell is keyboard/AT navigable (§6.9). The status strip moved UP into the console frame
 * (§11.4) — it persists across all modes, so it is no longer this component's concern. */

interface AppShellProps {
  map: ReactNode;
  list: ReactNode;
  video: ReactNode;
  missionLog: ReactNode;
}

export function AppShell({ map, list, video, missionLog }: AppShellProps) {
  // Craft layer (UI-overhaul pivot): the regions are now spaced, rounded, ELEVATED cards
  // floating on the warm paper ground — figure/ground from shadow + radius + air, not hairlines.
  // The map card is the largest (still the application); contacts over video on the right; the
  // mission log a foot card. `gap-3` + page padding give the composed, breathing rhythm.
  const card = "overflow-hidden rounded-lg bg-surface-1 shadow-card";
  return (
    <div className="flex h-full flex-col gap-3 bg-bg-base p-3 text-text-hi">
      {/* main: map-primary center + right rail (contacts over video) */}
      <div className="grid min-h-0 flex-1 grid-cols-[1fr_400px] gap-3">
        <section aria-label="Map" className={`relative min-h-0 ${card}`} data-region="map">
          {map}
        </section>

        <div className="grid min-h-0 grid-rows-[1fr_auto] gap-3">
          <section
            aria-label="Contacts"
            className={`min-h-0 overflow-auto ${card}`}
            data-region="list"
          >
            {list}
          </section>
          <section aria-label="Video" className={`min-h-0 ${card}`} data-region="video">
            {video}
          </section>
        </div>
      </div>

      {/* mission log — append-only foot card */}
      <section aria-label="Mission log" className={card} data-region="mission-log">
        {missionLog}
      </section>
    </div>
  );
}
