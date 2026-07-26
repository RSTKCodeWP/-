/**
 * Per-vehicle identity colour. Every fleet vehicle gets a stable default colour
 * derived from its sysid (so the same drone keeps the same colour across the
 * fleet strip, its map marker, and the waypoint groups assigned to it), and the
 * user can override any vehicle's colour. Overrides persist in localStorage so
 * an operator's colour scheme survives restarts.
 *
 * This is identity colour, distinct from the mode-category colour (getModeCategoryVar)
 * which encodes flight mode. Identity = "which drone", mode = "what is it doing".
 */

import { create } from 'zustand';

/**
 * Distinct, map-legible hues that read on both satellite imagery and the
 * light/dark UI surfaces. Ordered for maximum separation between adjacent
 * fleet members.
 */
export const VEHICLE_COLOR_PALETTE = [
  '#22d3ee', // cyan
  '#f59e0b', // amber
  '#a78bfa', // violet
  '#34d399', // emerald
  '#f472b6', // pink
  '#60a5fa', // blue
  '#fb923c', // orange
  '#a3e635', // lime
  '#e879f9', // fuchsia
  '#2dd4bf', // teal
] as const;

const STORAGE_KEY = 'ardudeck.vehicleColors';

function loadOverrides(): Record<string, string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, string>) : {};
  } catch {
    return {};
  }
}

function saveOverrides(overrides: Record<string, string>): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(overrides));
  } catch {
    /* storage unavailable - colours just won't persist */
  }
}

/** Stable default colour for a vehicle, by sysid. */
export function defaultVehicleColor(sysid: number): string {
  const len = VEHICLE_COLOR_PALETTE.length;
  const i = (((sysid - 1) % len) + len) % len;
  return VEHICLE_COLOR_PALETTE[i]!;
}

interface VehicleAppearanceStore {
  /** vehicleKey -> hex colour override. Absent = use the sysid default. */
  overrides: Record<string, string>;
  setColor: (vehicleKey: string, hex: string) => void;
  clearColor: (vehicleKey: string) => void;
}

export const useVehicleAppearanceStore = create<VehicleAppearanceStore>((set, get) => ({
  overrides: loadOverrides(),
  setColor: (vehicleKey, hex) => {
    const next = { ...get().overrides, [vehicleKey]: hex };
    saveOverrides(next);
    set({ overrides: next });
  },
  clearColor: (vehicleKey) => {
    const next = { ...get().overrides };
    delete next[vehicleKey];
    saveOverrides(next);
    set({ overrides: next });
  },
}));

/** Resolve a vehicle's effective colour: user override, else sysid default. */
export function resolveVehicleColor(
  overrides: Record<string, string>,
  vehicleKey: string,
  sysid: number,
): string {
  return overrides[vehicleKey] ?? defaultVehicleColor(sysid);
}

/** Hook form: subscribe to a single vehicle's effective colour. */
export function useVehicleColor(vehicleKey: string, sysid: number): string {
  return useVehicleAppearanceStore((s) => s.overrides[vehicleKey] ?? defaultVehicleColor(sysid));
}
