import { create } from 'zustand';
import type { PanelId } from '../components/panels';

/**
 * Bridge exposed by TelemetryDashboard so external systems (e.g. the tour
 * manager) can query/provision dockview panels without reaching into refs.
 */
export interface TelemetryLayoutBridge {
  hasPanel: (panelId: PanelId) => boolean;
  addPanel: (panelId: PanelId) => void;
  /** Bring an existing panel's tab to the front so its DOM is visible. */
  activatePanel: (panelId: PanelId) => void;
  loadPreset: (presetKey: string) => void;
}

interface TelemetryLayoutStore {
  bridge: TelemetryLayoutBridge | null;
  setBridge: (bridge: TelemetryLayoutBridge | null) => void;
}

export const useTelemetryLayoutStore = create<TelemetryLayoutStore>((set) => ({
  bridge: null,
  setBridge: (bridge) => set({ bridge }),
}));
