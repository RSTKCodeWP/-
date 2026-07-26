/**
 * Shared visual language for the fleet command surfaces (right-click menu, minimap, card
 * swatch popover). Uses the app's theme tokens so every surface follows light/dark mode
 * like the rest of the GCS. Floating panels over the map use the purpose-built
 * `surface-overlay` glass token - the same token the existing map popups use.
 */

/** Translucent glass panel that floats over the map / above the rail. */
export const TAC_GLASS = 'bg-surface-overlay backdrop-blur-md border border-subtle shadow-xl';

/** Idle / active treatment for a square command button (theme-aware). */
export const tacButton = (active: boolean): string =>
  active
    ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300'
    : 'bg-surface border-subtle text-content-secondary hover:bg-surface-raised hover:text-content';
