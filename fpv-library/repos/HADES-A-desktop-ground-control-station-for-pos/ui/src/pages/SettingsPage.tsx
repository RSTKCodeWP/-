import { BookOpen } from "lucide-react";

import { ThemeToggle } from "../components/ThemeToggle";

/* SET — Settings + Docs (DESIGN-SYSTEM §11.2). Sensor-error config, confirmation thresholds,
 * basemap/AO selection, the day/night theme toggle, and demo-vs-live live here; the Docs route
 * renders the shared P7 markdown (one source). Stage 3 lands the mode + the real theme toggle
 * (the one setting that's both locked-spec and immediately useful); Stage 4.4 builds the rest of
 * the forms via shadcn primitives against the iterate-against-render loop. */

export function SettingsPage({ onOpenDocs }: { onOpenDocs: () => void }) {
  return (
    <div data-testid="page-set" className="flex h-full justify-center overflow-auto bg-bg-base px-6 py-12">
      <div className="w-full max-w-xl space-y-6">
        <header className="space-y-1">
          <h1 className="font-ui text-2xl font-bold tracking-tight text-text-hi">Settings</h1>
          <p className="text-sm text-text-lo">
            Operational configuration and reference. Changes apply to this session.
          </p>
        </header>

        <section aria-label="Appearance" className="rounded-lg bg-surface-1 p-6 shadow-card">
          <h2 className="mb-4 font-ui text-2xs font-semibold uppercase tracking-[0.08em] text-text-lo">
            Appearance
          </h2>
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <p className="font-ui text-sm font-medium text-text-hi">Console theme</p>
              <p className="text-2xs text-text-lo">
                Day for sunlit field tents; Night for dark ops rooms.
              </p>
            </div>
            <ThemeToggle />
          </div>
        </section>

        <section aria-label="Documentation" className="rounded-lg bg-surface-1 p-6 shadow-card">
          <h2 className="mb-4 font-ui text-2xs font-semibold uppercase tracking-[0.08em] text-text-lo">
            Documentation
          </h2>
          <button
            type="button"
            onClick={onOpenDocs}
            className="flex items-center gap-2 rounded-sm bg-surface-2 px-4 py-2 font-ui text-sm font-medium text-text-mid outline-none transition-colors duration-micro hover:bg-surface-3 hover:text-text-hi focus-visible:shadow-focus"
          >
            <BookOpen size={15} aria-hidden /> Open HADES documentation
          </button>
        </section>
      </div>
    </div>
  );
}
