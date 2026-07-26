/**
 * @module checklist-store
 * @description Zustand store for pre-flight checklist state. Manages auto-verified
 * telemetry checks and manual pilot confirmation items. Provides go/no-go status
 * for arming.
 * @license GPL-3.0-only
 */

import { create } from "zustand";

export type ChecklistCategory = "hardware" | "software" | "environment" | "mission";
export type ChecklistItemType = "auto" | "manual";
export type ChecklistItemStatus = "pending" | "pass" | "fail" | "skipped";

export interface ChecklistItem {
  id: string;
  category: ChecklistCategory;
  label: string;
  description?: string;
  type: ChecklistItemType;
  status: ChecklistItemStatus;
  /** Display string for auto-check current value (e.g. "78%", "12 sats") */
  displayValue?: string;
}

/** Default checklist items. Order within category is display order. */
const DEFAULT_ITEMS: Omit<ChecklistItem, "status" | "displayValue">[] = [
  // Hardware
  { id: "battery-level", category: "hardware", label: "Battery charged", description: "Battery remaining > 20%", type: "auto" },
  { id: "battery-voltage", category: "hardware", label: "Battery voltage OK", description: "Voltage > 10.5V (3S minimum)", type: "auto" },
  { id: "props-secured", category: "hardware", label: "Props secured", description: "All propellers tightened and undamaged", type: "manual" },
  { id: "frame-intact", category: "hardware", label: "Frame intact", description: "No visible cracks or loose parts", type: "manual" },
  { id: "motors-free", category: "hardware", label: "Motors free to spin", description: "No obstructions on any motor", type: "manual" },

  // Software
  { id: "gps-fix", category: "software", label: "GPS lock acquired", description: "3D fix or better", type: "auto" },
  { id: "gps-sats", category: "software", label: "GPS satellites sufficient", description: "At least 8 satellites visible", type: "auto" },
  { id: "ekf-ok", category: "software", label: "EKF status OK", description: "EKF variance within limits", type: "auto" },
  { id: "sensors-healthy", category: "software", label: "Sensor health OK", description: "All present sensors reporting healthy", type: "auto" },
  { id: "prearm-pass", category: "software", label: "Firmware pre-arm pass", description: "No PreArm failures from FC", type: "auto" },

  // Environment
  { id: "wind-ok", category: "environment", label: "Wind conditions acceptable", description: "Wind speed within vehicle limits", type: "manual" },
  { id: "airspace-clear", category: "environment", label: "Airspace clear", description: "No manned aircraft or restricted zones", type: "manual" },
  { id: "launch-area-clear", category: "environment", label: "Launch area clear", description: "No people or obstacles in takeoff path", type: "manual" },
  { id: "observers-briefed", category: "environment", label: "Observers briefed", description: "All nearby personnel aware of flight", type: "manual" },

  // Mission
  { id: "flight-plan", category: "mission", label: "Flight plan loaded", description: "Mission waypoints uploaded or confirmed", type: "auto" },
  { id: "geofence-set", category: "mission", label: "Geofence set", description: "Geofence enabled with appropriate limits", type: "auto" },
  { id: "rtl-point", category: "mission", label: "Return-to-launch set", description: "RTL point confirmed and safe", type: "manual" },
  { id: "emergency-reviewed", category: "mission", label: "Emergency procedures reviewed", description: "Pilot knows abort, RTL, and kill procedures", type: "manual" },
];

interface ChecklistStoreState {
  items: ChecklistItem[];
  sessionId: string | null;
  startedAt: number | null;
  completedAt: number | null;

  startSession: () => void;
  resetSession: () => void;
  toggleManualItem: (id: string) => void;
  updateAutoItem: (id: string, status: "pass" | "fail", displayValue?: string) => void;
  skipItem: (id: string) => void;
  isReadyToArm: () => boolean;
  getProgress: () => { total: number; checked: number; failed: number };
  getCategoryProgress: (category: ChecklistCategory) => { total: number; checked: number; failed: number };
}

export const useChecklistStore = create<ChecklistStoreState>((set, get) => ({
  items: DEFAULT_ITEMS.map((item) => ({ ...item, status: "pending" as const })),
  sessionId: null,
  startedAt: null,
  completedAt: null,

  startSession: () => {
    set({
      items: DEFAULT_ITEMS.map((item) => ({ ...item, status: "pending" as const })),
      sessionId: crypto.randomUUID(),
      startedAt: Date.now(),
      completedAt: null,
    });
  },

  resetSession: () => {
    set({
      items: DEFAULT_ITEMS.map((item) => ({ ...item, status: "pending" as const })),
      sessionId: null,
      startedAt: null,
      completedAt: null,
    });
  },

  toggleManualItem: (id) => {
    set((state) => ({
      items: state.items.map((item) => {
        if (item.id !== id || item.type !== "manual") return item;
        return {
          ...item,
          status: item.status === "pass" ? "pending" : "pass",
        };
      }),
    }));
  },

  updateAutoItem: (id, status, displayValue) => {
    set((state) => ({
      items: state.items.map((item) => {
        if (item.id !== id || item.type !== "auto") return item;
        return { ...item, status, displayValue };
      }),
    }));
  },

  skipItem: (id) => {
    set((state) => ({
      items: state.items.map((item) => {
        if (item.id !== id) return item;
        return { ...item, status: item.status === "skipped" ? "pending" : "skipped" };
      }),
    }));
  },

  isReadyToArm: () => {
    const { items } = get();
    return items.every((item) => item.status === "pass" || item.status === "skipped");
  },

  getProgress: () => {
    const { items } = get();
    return {
      total: items.length,
      checked: items.filter((i) => i.status === "pass" || i.status === "skipped").length,
      failed: items.filter((i) => i.status === "fail").length,
    };
  },

  getCategoryProgress: (category) => {
    const items = get().items.filter((i) => i.category === category);
    return {
      total: items.length,
      checked: items.filter((i) => i.status === "pass" || i.status === "skipped").length,
      failed: items.filter((i) => i.status === "fail").length,
    };
  },
}));
