/**
 * Map markers for every non-active vehicle. The active vehicle keeps its existing detailed
 * marker (heading/speed DOM dynamics, trail, command popup, drawn topmost); this overlay
 * draws the rest of the fleet so the whole picture is on one map. Clicking a fleet marker
 * makes that vehicle active.
 *
 * GROUPING (declutter): when vehicles overlap on screen - which is what happens as you zoom
 * OUT, or when they share a spot like SITL at one home - their markers and labels pile into
 * an unreadable stack. We detect overlapping groups in screen space and pull the members in
 * around a MAIN vehicle:
 *   - the main is the formation leader (if a formation is active), else the active/selected
 *     vehicle, else the lowest sysid. It stays full size at its true position with its full
 *     label; everyone else is drawn smaller and tucked in close around it.
 *   - followers sit at their REAL bearing from the main, so the cluster resembles the actual
 *     formation (a vee stays a vee). When the group is genuinely stacked on one point (no
 *     real geometry, e.g. SITL home) we fall back to an even ring.
 * Each follower gets a thin leader line back to its true position and a COMPACT label (just
 * the SYS id, expanding to the full readout on hover). Zoomed in, vehicles separate in pixels
 * so nothing groups - you see real positions at full size.
 *
 * Rendered inside the telemetry MapContainer.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import { createTacticalVehicleIcon, updateTacticalIconDOM } from '../map/TacticalVehicleIcon';
import { useFleetVehicles, selectActiveVehicle, type FleetVehicle } from '../../hooks/useFleet';
import { useActiveVehicleStore } from '../../stores/active-vehicle-store';
import { useFormationStore } from '../../stores/formation-store';
import { useVehicleColor } from '../../stores/vehicle-appearance-store';
import { useSettingsStore } from '../../stores/settings-store';
import { formatAltitudeFromMeters, formatSpeedFromMetersPerSecond } from '../../../shared/user-units.js';

const ICON_SIZE = 52;
const ICON_CENTER = ICON_SIZE / 2;
/** Markers whose centres are closer than this (px) are treated as overlapping. */
const OVERLAP_PX = 46;
/** Hard cap on how far apart (m) two vehicles can be and still group. Pixels alone aren't
 *  enough: when zoomed way out, a vehicle a kilometre away can fall within OVERLAP_PX and get
 *  wrongly tucked into a cluster it isn't part of. Grouping means "actually near", not just
 *  "near on screen". Well above any real formation spread, well below a strayed vehicle. */
const MAX_CLUSTER_SPREAD_M = 250;
/** Followers are drawn at this scale so the main vehicle reads as the focus. */
const FOLLOWER_SCALE = 0.6;
/** Distance (px) from the main to each follower's centre - tight, so they almost touch. */
const RING_RADIUS = 32;
/** Below this real separation (m) a group is "stacked on one point" -> even ring fallback. */
const MIN_SPREAD_M = 2;
/** The main's info label box sits to its right (east). Reserve this sector (deg, ±around
 *  east) so followers never tuck in behind the box - they're pushed to the arc edge. */
const LABEL_KEEPOUT_DEG = 65;

type Offset = { dx: number; dy: number; scale: number; main: boolean };

/** Approx ground distance between two [lat,lon] points, metres (equirectangular). */
function geoDistM(a: [number, number], b: [number, number]): number {
  const lat = (a[0] * Math.PI) / 180;
  const dLat = ((b[0] - a[0]) * Math.PI) / 180;
  const dLon = ((b[1] - a[1]) * Math.PI) / 180 * Math.cos(lat);
  return Math.sqrt(dLat * dLat + dLon * dLon) * 6371000;
}

/** Screen-space bearing (radians) from one [lat,lon] to another: 0 = east, -PI/2 = north.
 *  Derived from lat/lon (not pixels), so the fan arrangement is identical at every zoom. */
function screenBearing(from: [number, number], to: [number, number]): number {
  const lat = (from[0] * Math.PI) / 180;
  const dNorth = to[0] - from[0];
  const dEast = (to[1] - from[1]) * Math.cos(lat);
  return Math.atan2(-dNorth, dEast);
}

/**
 * Screen-space grouping offsets. Projects every vehicle to layer points, greedily groups the
 * ones that overlap, picks each group's main (leader > active > lowest sysid), keeps the main
 * at its true point, and rings the followers in close around it - at their true bearing when
 * the group has real spread, else evenly. Offsets are screen px (constant across zoom),
 * recomputed on zoom/pan and whenever positions change.
 */
function useFanOffsets(
  vehicles: FleetVehicle[],
  map: L.Map,
  leaderKeys: ReadonlySet<string>,
  activeKey: string | null,
): Record<string, Offset> {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const bump = () => setTick((t) => t + 1);
    map.on('zoomend', bump);
    map.on('moveend', bump);
    return () => {
      map.off('zoomend', bump);
      map.off('moveend', bump);
    };
  }, [map]);

  return useMemo(() => {
    const pts = vehicles
      .filter((v) => v.position)
      .map((v) => {
        const p = map.latLngToLayerPoint(v.position as [number, number]);
        return { v, x: p.x, y: p.y, used: false };
      });

    const offsets: Record<string, Offset> = {};
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i];
      if (!a || a.used) continue;
      a.used = true;
      const members = [a];
      for (let j = i + 1; j < pts.length; j++) {
        const b = pts[j];
        if (!b || b.used) continue;
        const nearOnScreen = Math.hypot(a.x - b.x, a.y - b.y) < OVERLAP_PX;
        const nearOnGround = geoDistM(a.v.position as [number, number], b.v.position as [number, number]) < MAX_CLUSTER_SPREAD_M;
        if (nearOnScreen && nearOnGround) {
          b.used = true;
          members.push(b);
        }
      }
      if (members.length < 2) continue;

      // Main: formation leader, else active/selected, else lowest sysid.
      let main = members.find((m) => leaderKeys.has(m.v.key)) || members.find((m) => m.v.key === activeKey);
      if (!main) {
        main = members[0];
        for (const m of members) if (main && m.v.sysid < main.v.sysid) main = m;
      }
      if (!main) continue;

      const anchor = main;
      const anchorPos = anchor.v.position as [number, number];
      const followers = members.filter((m) => m !== anchor);
      const span = 360 - 2 * LABEL_KEEPOUT_DEG; // arc available once the label sector is reserved
      followers.forEach((f, idx) => {
        // Real bearing from the main when the group has actual geometry (zoom-invariant);
        // an even ring only when the vehicles are genuinely stacked on one point (SITL home).
        const apart = geoDistM(anchorPos, f.v.position as [number, number]) > MIN_SPREAD_M;
        let deg: number;
        if (apart) {
          deg = (screenBearing(anchorPos, f.v.position as [number, number]) * 180) / Math.PI; // 0=east
          // Nudge an east-pointing follower out of the label box's sector (keeps it visible).
          if (Math.abs(deg) < LABEL_KEEPOUT_DEG) deg = deg >= 0 ? LABEL_KEEPOUT_DEG : -LABEL_KEEPOUT_DEG;
        } else {
          // Even ring across the arc that avoids the label box (east).
          deg = LABEL_KEEPOUT_DEG + ((idx + 0.5) / followers.length) * span;
        }
        const ang = (deg * Math.PI) / 180;
        offsets[f.v.key] = {
          dx: anchor.x + RING_RADIUS * Math.cos(ang) - f.x,
          dy: anchor.y + RING_RADIUS * Math.sin(ang) - f.y,
          scale: FOLLOWER_SCALE,
          main: false,
        };
      });
      offsets[anchor.v.key] = { dx: 0, dy: 0, scale: 1, main: true };
    }
    return offsets;
  }, [vehicles, map, tick, leaderKeys, activeKey]);
}

/**
 * One fleet marker. The icon is memoized on its VISUAL fields only, so a position tick
 * (several times a second) moves the marker without rebuilding the DivIcon DOM - that
 * rebuild is what made the icon flicker. Heading/speed/altitude are this vehicle's OWN live
 * values, applied by DOM mutation so every fleet icon shows its own telemetry, not zeros.
 */
function FleetMarker({ v, isLeader, offset }: { v: FleetVehicle; isLeader: boolean; offset?: Offset }) {
  const markerRef = useRef<L.Marker | null>(null);
  const identityColor = useVehicleColor(v.key, v.sysid);
  const altitudeUnit = useSettingsStore((s) => s.unitPreferences.altitude);
  const speedUnit = useSettingsStore((s) => s.unitPreferences.speed);
  const isMain = offset?.main ?? false;
  const icon = useMemo(
    () => createTacticalVehicleIcon({
      vehicleClass: v.vehicleClass,
      state: v.state,
      selected: false,
      mode: v.mode,
      designation: v.label,
      isLeader,
      bodyColor: identityColor,
      // The group's main shows its full label; everyone else collapses to the SYS id chip.
      compact: !isMain,
    }),
    [v.vehicleClass, v.state, v.mode, v.label, isLeader, identityColor, isMain],
  );

  useEffect(() => {
    const el = markerRef.current?.getElement();
    if (!el) return;
    updateTacticalIconDOM(el, {
      heading: v.heading,
      groundspeed: v.groundspeed,
      speedText: formatSpeedFromMetersPerSecond(v.groundspeed, speedUnit),
      altitudeAgl: v.altitudeAgl,
      altitudeText: formatAltitudeFromMeters(v.altitudeAgl, altitudeUnit),
    }, v.vehicleClass === 'antenna');
  }, [v.heading, v.groundspeed, v.altitudeAgl, v.vehicleClass, icon, speedUnit, altitudeUnit]);

  // Apply the grouping offset: translate + scale the icon content to its tucked-in position
  // and draw a dashed leader line from the true map point (marker centre) to it. Reapplied
  // when the icon DOM is rebuilt (icon dep) or the offset changes.
  const dx = offset?.dx ?? 0;
  const dy = offset?.dy ?? 0;
  const scale = offset?.scale ?? 1;
  useEffect(() => {
    const el = markerRef.current?.getElement();
    if (!el) return;
    // A tucked-in follower hides its label until hover (see .tvi-grouped in globals.css).
    el.classList.toggle('tvi-grouped', !!offset && !offset.main);
    const content = el.querySelector<HTMLElement>('.tactical-vehicle-icon');
    if (content) content.style.transform = dx || dy || scale !== 1 ? `translate(${dx}px,${dy}px) scale(${scale})` : '';

    let line = el.querySelector<SVGSVGElement>('svg.tvi-leader');
    if (dx || dy) {
      if (!line) {
        line = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        line.setAttribute('class', 'tvi-leader');
        line.setAttribute('width', String(ICON_SIZE));
        line.setAttribute('height', String(ICON_SIZE));
        line.innerHTML = '<line stroke="rgba(148,163,184,0.55)" stroke-width="1.5" stroke-dasharray="3 3" />';
        el.insertBefore(line, el.firstChild);
      }
      const ln = line.firstElementChild as SVGLineElement;
      ln.setAttribute('x1', String(ICON_CENTER));
      ln.setAttribute('y1', String(ICON_CENTER));
      ln.setAttribute('x2', String(ICON_CENTER + dx));
      ln.setAttribute('y2', String(ICON_CENTER + dy));
      line.style.display = '';
    } else if (line) {
      line.style.display = 'none';
    }
  }, [dx, dy, scale, icon]);

  return (
    <Marker
      ref={markerRef}
      position={v.position as [number, number]}
      zIndexOffset={4000}
      icon={icon}
      eventHandlers={{
        click: (e) => {
          L.DomEvent.stopPropagation(e.originalEvent);
          selectActiveVehicle(v.key, v.transportId);
        },
        contextmenu: (e) => {
          L.DomEvent.stopPropagation(e.originalEvent);
          L.DomEvent.preventDefault(e.originalEvent);
          useFormationStore.getState().openContextMenu({
            x: e.originalEvent.clientX,
            y: e.originalEvent.clientY,
            vehicleKey: v.key,
          });
        },
      }}
    />
  );
}

export function FleetMarkers() {
  const vehicles = useFleetVehicles();
  const formations = useActiveVehicleStore((s) => s.formations);
  const activeVehicleKey = useActiveVehicleStore((s) => s.activeVehicleKey);
  const map = useMap();
  const leaderKeys = useMemo(() => new Set(Object.keys(formations)), [formations]);
  const offsets = useFanOffsets(vehicles, map, leaderKeys, activeVehicleKey);

  return (
    <>
      {vehicles
        .filter((v) => !v.isActive && v.position !== null)
        .map((v) => (
          <FleetMarker key={v.key} v={v} isLeader={leaderKeys.has(v.key)} offset={offsets[v.key]} />
        ))}
    </>
  );
}
