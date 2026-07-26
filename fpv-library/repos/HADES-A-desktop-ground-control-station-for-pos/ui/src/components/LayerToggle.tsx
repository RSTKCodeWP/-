import { useLayerStore, type LayerKey } from "../store/layers";

/* Map layer toggles (impl-plan Task 5.5d) — the operator declutters the context layers
 * under load. Pins are deliberately NOT toggleable (a survivor must never be hidden). A
 * small overlay control on the map; accessible switches (keyboard + ARIA). */

const LAYERS: { key: LayerKey; label: string }[] = [
  { key: "coverage", label: "Coverage" },
  { key: "track", label: "Track" },
  { key: "footprint", label: "Footprint" },
  { key: "uncertainty", label: "Uncertainty" },
];

export function LayerToggle() {
  const visible = useLayerStore((s) => s.visible);
  const toggle = useLayerStore((s) => s.toggle);

  return (
    <div
      className="pointer-events-auto absolute left-2 top-2 flex flex-col gap-1 rounded-md border border-hairline bg-surface-1/95 p-2 font-mono text-2xs"
      style={{ zIndex: "var(--z-map-overlay)" }}
      role="group"
      aria-label="Map layers"
    >
      {LAYERS.map(({ key, label }) => (
        <button
          key={key}
          role="switch"
          aria-checked={visible[key]}
          aria-label={label}
          onClick={() => toggle(key)}
          className="flex items-center gap-2 rounded-sm px-1 py-0.5 text-left text-text-mid outline-none hover:bg-surface-2 focus-visible:shadow-focus"
        >
          <span
            aria-hidden
            className={`h-2 w-2 rounded-pill ${visible[key] ? "bg-blue-bright" : "bg-surface-3"}`}
          />
          {label}
        </button>
      ))}
    </div>
  );
}
