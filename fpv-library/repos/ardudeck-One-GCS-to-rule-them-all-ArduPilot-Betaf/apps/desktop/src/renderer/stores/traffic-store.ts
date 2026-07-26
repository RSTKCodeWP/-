/**
 * traffic-store — live ADS-B/OGN contacts for the map overlays.
 *
 * The main process owns all providers and pushes TrafficBatch snapshots; this
 * store just holds the latest snapshot + proximity thresholds and forwards
 * viewport/enable changes. Proximity severity is computed per-frame in the
 * overlays (it depends on the fast-updating own-vehicle position), so the store
 * stays lean. initTrafficStore() wires the push subscription and mirrors the
 * 'traffic'/'gliders' overlay toggles to the backend; it is idempotent so every
 * map surface can call it on mount.
 */

import { create } from 'zustand';
import type { TrafficContact, TrafficSource, AlertZone } from '../../shared/traffic-types';
import { DEFAULT_TRAFFIC_CONFIG } from '../../shared/traffic-types';
import { useOverlayStore } from './overlay-store';
import { evaluateZones, intrusionKey } from '../components/map/traffic/zone-alerts';

/** A logged perimeter intrusion (a contact entering an alert zone). */
export interface ZoneAlert {
  id: string;
  zoneId: string;
  zoneName: string;
  contactId: string;
  label: string;
  source: TrafficSource;
  altMeters?: number;
  at: number;
  /** Cleared once the contact leaves the zone (kept in the log, dimmed). */
  active: boolean;
}

const MAX_ALERTS = 50;

interface TrafficStore {
  contacts: TrafficContact[];
  proximity: { rangeMeters: number; verticalMeters: number };
  altitudeBand: { floorMeters: number; ceilingMeters: number; hardCeiling: boolean };
  iconScale: number;
  /** Perimeter alert zones (mirrors TrafficConfig.alertZones). */
  alertZones: AlertZone[];
  /** Contact ids currently inside any zone (for map highlighting). */
  intrudingContactIds: Set<string>;
  /** Zone ids that currently contain at least one contact (red perimeter). */
  intrudingZoneIds: Set<string>;
  /** Rolling log of zone entries, newest first. */
  alerts: ZoneAlert[];
  /** Last reported map centre, used to seed new alert zones from the settings card. */
  viewportCenter: { lat: number; lon: number } | null;
  setContacts: (contacts: TrafficContact[]) => void;
  setProximity: (p: { rangeMeters: number; verticalMeters: number }) => void;
  setAltitudeBand: (b: { floorMeters: number; ceilingMeters: number; hardCeiling: boolean }) => void;
  setIconScale: (s: number) => void;
  setAlertZones: (zones: AlertZone[]) => void;
  dismissAlerts: () => void;
}

// Module-level so it survives re-renders: the set of (zone::contact) pairs that
// were inside a zone last frame, used to fire one alert per fresh entry.
let prevIntrusions = new Set<string>();
let alertSeq = 0;

export const useTrafficStore = create<TrafficStore>((set, get) => ({
  contacts: [],
  proximity: { ...DEFAULT_TRAFFIC_CONFIG.proximity },
  altitudeBand: { ...DEFAULT_TRAFFIC_CONFIG.altitudeFilter },
  iconScale: DEFAULT_TRAFFIC_CONFIG.iconScale,
  alertZones: [],
  intrudingContactIds: new Set(),
  intrudingZoneIds: new Set(),
  alerts: [],
  viewportCenter: null,
  setContacts: (contacts) => {
    const { alertZones, alerts } = get();
    if (alertZones.length === 0) {
      if (prevIntrusions.size > 0) prevIntrusions = new Set();
      set({ contacts });
      return;
    }
    const { current, byZone } = evaluateZones(contacts, alertZones);
    // Fresh entries = currently-inside pairs that were not inside last frame.
    const newAlerts: ZoneAlert[] = [];
    for (const zone of alertZones) {
      const inSet = byZone.get(zone.id);
      if (!inSet) continue;
      for (const cid of inSet) {
        const key = intrusionKey(zone.id, cid);
        if (prevIntrusions.has(key)) continue;
        const c = contacts.find((x) => x.id === cid);
        if (!c) continue;
        newAlerts.push({
          id: `za-${++alertSeq}`,
          zoneId: zone.id,
          zoneName: zone.name,
          contactId: cid,
          label: c.callsign ?? c.registration ?? c.uasId ?? c.id,
          source: c.source,
          ...(c.altMeters !== undefined ? { altMeters: c.altMeters } : {}),
          at: Date.now(),
          active: true,
        });
      }
    }
    // Mark logged alerts still-inside as active, the rest as cleared.
    const updated = alerts.map((a) => ({ ...a, active: current.has(intrusionKey(a.zoneId, a.contactId)) }));
    const merged = [...newAlerts, ...updated].slice(0, MAX_ALERTS);
    const intruding = new Set<string>();
    for (const ids of byZone.values()) for (const id of ids) intruding.add(id);
    prevIntrusions = current;
    set({ contacts, alerts: merged, intrudingContactIds: intruding, intrudingZoneIds: new Set(byZone.keys()) });
  },
  setProximity: (proximity) => set({ proximity }),
  setAltitudeBand: (altitudeBand) => set({ altitudeBand }),
  setIconScale: (iconScale) => set({ iconScale }),
  setAlertZones: (alertZones) => set({ alertZones }),
  dismissAlerts: () => set({ alerts: [] }),
}));

/** Map the two overlay toggles to traffic sources. */
function sourceForOverlay(id: string): TrafficSource | null {
  if (id === 'traffic') return 'adsb';
  if (id === 'gliders') return 'ogn';
  if (id === 'remoteid') return 'remoteid';
  return null;
}

let initialized = false;

export function initTrafficStore(): void {
  if (initialized || typeof window === 'undefined' || !window.electronAPI?.onTrafficUpdate) return;
  initialized = true;

  window.electronAPI.onTrafficUpdate((batch) => {
    useTrafficStore.getState().setContacts(batch.contacts);
  });

  // Pull persisted proximity thresholds + altitude band + alert zones.
  void window.electronAPI.getTrafficConfig().then((cfg) => {
    if (cfg?.proximity) useTrafficStore.getState().setProximity(cfg.proximity);
    if (cfg?.altitudeFilter) useTrafficStore.getState().setAltitudeBand(cfg.altitudeFilter);
    if (cfg?.iconScale) useTrafficStore.getState().setIconScale(cfg.iconScale);
    if (cfg?.alertZones) useTrafficStore.getState().setAlertZones(cfg.alertZones);
  });

  // Mirror overlay toggle state -> backend enable. Drive the initial state and
  // every change so providers start/stop with the toggles.
  let prev = new Set<TrafficSource>();
  const sync = (active: Set<string>): void => {
    const next = new Set<TrafficSource>();
    for (const id of active) {
      const src = sourceForOverlay(id);
      if (src) next.add(src);
    }
    for (const src of next) if (!prev.has(src)) window.electronAPI.setTrafficEnabled(src, true);
    for (const src of prev) if (!next.has(src)) window.electronAPI.setTrafficEnabled(src, false);
    prev = next;
  };
  sync(useOverlayStore.getState().activeOverlays);
  useOverlayStore.subscribe((s) => sync(s.activeOverlays));
}

let viewportTimer: number | null = null;

/** Debounced viewport report so providers scope their queries to the view. */
export function reportTrafficViewport(lat: number, lon: number, radiusKm: number): void {
  if (!window.electronAPI?.setTrafficViewport) return;
  if (viewportTimer !== null) window.clearTimeout(viewportTimer);
  viewportTimer = window.setTimeout(() => {
    window.electronAPI.setTrafficViewport({ lat, lon, radiusKm });
    // Seed the alert-zone center from the debounced view, NOT synchronously on
    // every moveend: map auto-follow (fleet mode) fires moveend on every tick,
    // and a synchronous store write there can feed a re-render -> re-fit loop.
    // Only write when the centre actually moved.
    const prev = useTrafficStore.getState().viewportCenter;
    if (!prev || Math.abs(prev.lat - lat) > 1e-6 || Math.abs(prev.lon - lon) > 1e-6) {
      useTrafficStore.setState({ viewportCenter: { lat, lon } });
    }
  }, 500);
}
