/**
 * Fleet strip - a collapsible tactical rail of vehicle rows on the left edge of the
 * telemetry view. Shows every connected vehicle (registry + live telemetry), lets the
 * operator pick the active vehicle (click a row), multi-select for group commands (a
 * checkbox that surfaces on hover), and right-click a row for formation orders. Dense and
 * low-chrome - a command console, not a web form - and follows the app's light/dark
 * theme. Renders nothing for a single vehicle.
 */

import { useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useFleetVehicles, selectActiveVehicle, deselectActiveVehicle, type FleetVehicle } from '../../hooks/useFleet';
import { useActiveVehicleStore } from '../../stores/active-vehicle-store';
import { useVehicleColor, useVehicleAppearanceStore, VEHICLE_COLOR_PALETTE } from '../../stores/vehicle-appearance-store';
import { useTelemMissionViewStore } from '../../stores/telem-mission-view-store';
import { STATE_COLORS, getModeCategoryVar } from '../map/tactical-icon-pool';
import { AirframeIcon, airframeLabel } from '../map/airframe-icon';
import { FleetGroupActions } from './FleetGroupActions';
import { FleetCoordination } from './FleetCoordination';
import { FleetContextMenu } from './FleetContextMenu';
import { useFormationStore } from '../../stores/formation-store';
import { HeartbeatDot } from './HeartbeatDot';
import { TAC_GLASS } from './tactical';

function BatteryPip({ pct }: { pct: number | null }) {
  if (pct === null) return <span className="text-content-tertiary text-[9px] font-mono">--</span>;
  // Darker shades stay legible on a light card AND visible on a dark one.
  const color = pct < 20 ? '#dc2626' : pct < 40 ? '#d97706' : '#16a34a';
  return (
    <div className="flex items-center gap-1">
      <div className="w-6 h-1 rounded-full overflow-hidden bg-surface-inset">
        <div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, pct))}%`, background: color }} />
      </div>
      <span className="font-mono text-[10px] font-semibold" style={{ color }}>{Math.round(pct)}</span>
    </div>
  );
}

function FleetCard({ v, role }: { v: FleetVehicle; role?: 'leader' | 'wingman' }) {
  const toggleSelected = useActiveVehicleStore((s) => s.toggleSelected);
  const openContextMenu = useFormationStore((s) => s.openContextMenu);
  const setColor = useVehicleAppearanceStore((s) => s.setColor);
  const identityColor = useVehicleColor(v.key, v.sysid);
  const stateColor = STATE_COLORS[v.state];
  const [swatchOpen, setSwatchOpen] = useState(false);
  const [swatchPos, setSwatchPos] = useState<{ top: number; left: number } | null>(null);
  const swatchRef = useRef<HTMLButtonElement>(null);

  return (
    <div
      onClick={() => (v.isActive ? deselectActiveVehicle() : selectActiveVehicle(v.key, v.transportId))}
      onContextMenu={(e) => { e.preventDefault(); openContextMenu({ x: e.clientX, y: e.clientY, vehicleKey: v.key }); }}
      className={`group relative flex items-center gap-2 cursor-pointer rounded border pl-2 pr-1.5 py-1 transition-colors ${
        v.isActive ? 'border-cyan-500/50 bg-cyan-500/10' : 'border-subtle bg-surface hover:bg-surface-raised'
      }`}
      data-tip={v.isActive ? `${v.label} - click to deselect` : `${v.label} - ${v.mode}${v.armed ? ' - ARMED' : ''}`}
    >
      {/* Identity colour bar - matches this vehicle's map marker + its waypoints */}
      <span className="absolute left-0 top-1 bottom-1 w-0.5 rounded-full" style={{ background: identityColor }} />

      {/* Airframe pictogram tinted with identity colour; ring shows STATE (gold = leader).
          Click opens the identity-colour palette. */}
      <button
        ref={swatchRef}
        onClick={(e) => {
          e.stopPropagation();
          const r = swatchRef.current?.getBoundingClientRect();
          if (r) setSwatchPos({ top: r.bottom + 4, left: r.left });
          setSwatchOpen((o) => !o);
        }}
        className="relative shrink-0 grid place-items-center w-6 h-6 rounded"
        style={{
          color: identityColor,
          background: 'var(--bg-inset)',
          boxShadow: `0 0 0 1.5px ${role === 'leader' ? '#f59e0b' : stateColor.fill}`,
        }}
        data-tip={`${airframeLabel(v.mavType)} - ${v.state} (click to set identity colour)`}
      >
        <AirframeIcon mavType={v.mavType} size={16} />
      </button>
      {swatchOpen && swatchPos &&
        createPortal(
          <>
            <div className="fixed inset-0 z-[998]" onClick={(e) => { e.stopPropagation(); setSwatchOpen(false); }} />
            <div
              className={`fixed z-[999] p-2 rounded-md grid grid-cols-5 gap-1.5 ${TAC_GLASS}`}
              style={{ top: swatchPos.top, left: swatchPos.left }}
              onClick={(e) => e.stopPropagation()}
            >
              {VEHICLE_COLOR_PALETTE.map((c) => (
                <button
                  key={c}
                  onClick={() => { setColor(v.key, c); setSwatchOpen(false); }}
                  className={`w-5 h-5 rounded transition-transform hover:scale-110 ${c === identityColor ? 'ring-2 ring-white' : ''}`}
                  style={{ backgroundColor: c }}
                  aria-label={`Set colour ${c}`}
                />
              ))}
            </div>
          </>,
          document.body,
        )}

      {/* Identity */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[11px] font-semibold text-content truncate">{v.label}</span>
          {role === 'leader' && (
            <span className="text-[7px] font-bold uppercase tracking-wide px-1 rounded-sm bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">Lead</span>
          )}
          <span className="ml-auto font-mono text-[10px] font-semibold truncate" style={{ color: getModeCategoryVar(v.mode) }}>{v.mode}</span>
        </div>
        <div className="flex items-center gap-1.5 mt-0.5">
          <BatteryPip pct={v.batteryPct} />
          <span className="text-[8px] uppercase tracking-wide text-content-tertiary">{airframeLabel(v.mavType)}</span>
          <HeartbeatDot lastUpdate={v.lastUpdate} className="ml-auto scale-75 origin-right" />
        </div>
      </div>

      {/* Multi-select - surfaces on hover (or when selected); hidden for wingmen. */}
      {!role && (
        <input
          type="checkbox"
          checked={v.isSelected}
          onClick={(e) => e.stopPropagation()}
          onChange={() => toggleSelected(v.key)}
          className={`shrink-0 accent-cyan-500 w-3 h-3 transition-opacity ${v.isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
          data-tip="Select for group commands"
        />
      )}

      {/* Orders affordance - a chevron that fades in on hover so the operator knows there's
          a menu here (also reachable by right-clicking anywhere on the row). */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          const r = e.currentTarget.getBoundingClientRect();
          openContextMenu({ x: r.right + 4, y: r.top, vehicleKey: v.key });
        }}
        data-tip="Orders"
        className="shrink-0 grid place-items-center w-4 h-5 rounded text-content-tertiary hover:text-content hover:bg-surface-raised opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none"><path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
    </div>
  );
}

export function FleetStrip() {
  const vehicles = useFleetVehicles();
  const formations = useActiveVehicleStore((s) => s.formations);
  const [collapsed, setCollapsed] = useState(false);

  // Single-vehicle (or none): render nothing, keep the classic layout.
  if (vehicles.length < 2) return null;

  if (collapsed) {
    return (
      <div className="shrink-0 w-8 border-r border-subtle bg-surface-nav flex flex-col items-center py-2 gap-2">
        <button onClick={() => setCollapsed(false)} className="text-content-secondary hover:text-content text-xs" data-tip="Expand fleet">{'»'}</button>
        {vehicles.map((v) => (
          <span
            key={v.key}
            onClick={() => selectActiveVehicle(v.key, v.transportId)}
            onContextMenu={(e) => { e.preventDefault(); useFormationStore.getState().openContextMenu({ x: e.clientX, y: e.clientY, vehicleKey: v.key }); }}
            className={`w-3 h-3 rounded-full cursor-pointer ${v.isActive ? 'ring-2 ring-cyan-400' : ''}`}
            style={{ background: STATE_COLORS[v.state].fill }}
            data-tip={`${v.label} - ${v.mode}`}
          />
        ))}
        <FleetContextMenu />
      </div>
    );
  }

  const sorted = [...vehicles].sort((a, b) => a.sysid - b.sysid);
  // One nested block per formation (leader card + its wingmen indented under it);
  // vehicles in no formation stay free, selectable cards below the groups.
  const inFormation = new Set(Object.values(formations).flat());
  const groups = Object.entries(formations)
    .map(([leaderKey, memberKeys]) => ({
      leader: sorted.find((v) => v.key === leaderKey),
      wingmen: sorted.filter((v) => v.key !== leaderKey && memberKeys.includes(v.key)),
    }))
    .filter((g): g is { leader: FleetVehicle; wingmen: FleetVehicle[] } => !!g.leader)
    .sort((a, b) => a.leader.sysid - b.leader.sysid);
  const others = sorted.filter((v) => !inFormation.has(v.key));

  return (
    <div className="shrink-0 w-52 border-r border-subtle bg-surface-nav flex flex-col text-content">
      <div className="flex items-center justify-between px-2.5 py-2 border-b border-subtle">
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-content-secondary">
          Fleet <span className="text-content-tertiary">·</span> <span className="font-mono text-content">{vehicles.length}</span>
        </span>
        <button onClick={() => setCollapsed(true)} className="text-content-secondary hover:text-content text-xs" data-tip="Collapse fleet">{'«'}</button>
      </div>

      <div className="flex-1 overflow-y-auto p-1.5 flex flex-col gap-1">
        {groups.map((g) => (
          <div key={g.leader.key} className="flex flex-col gap-1">
            <FleetCard v={g.leader} role="leader" />
            {g.wingmen.length > 0 && (
              <div className="ml-1.5 border-l border-subtle pl-1.5 flex flex-col gap-1">
                {g.wingmen.map((v) => (
                  <FleetCard key={v.key} v={v} role="wingman" />
                ))}
              </div>
            )}
          </div>
        ))}
        {others.map((v) => <FleetCard key={v.key} v={v} />)}
      </div>

      <FleetCoordination />
      <FleetGroupActions />
      <FleetContextMenu />
    </div>
  );
}
