/* A designed empty/loading state — intentional, never a bare spinner or blank panel
 * (DESIGN-SYSTEM anti-slop #7). Used for "No contacts yet", "Connecting to service",
 * "No fix (CUE-ONLY)", etc. Quiet, centered, instrument-grade. */

interface PlaceholderProps {
  label: string;
  hint?: string;
}

export function Placeholder({ label, hint }: PlaceholderProps) {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-2 p-6 text-center">
      <span className="text-sm font-medium text-text-mid">{label}</span>
      {hint ? <span className="font-mono text-2xs text-text-lo">{hint}</span> : null}
    </div>
  );
}
