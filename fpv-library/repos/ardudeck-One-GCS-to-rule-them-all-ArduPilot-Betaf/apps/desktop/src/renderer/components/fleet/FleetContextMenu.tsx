/**
 * Right-click menu for fleet vehicles - opened from a rail row (FleetStrip) or a map
 * marker (FleetMarkers), both writing the target into the formation store. Dark tactical
 * glass. Mirrors the rail/dock: "Command this vehicle", "Set as leader", a row of
 * one-click shape glyphs (form up on THIS vehicle), and Break formation.
 */

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useFormationStore } from '../../stores/formation-store';
import { formationOf } from '../../stores/active-vehicle-store';
import { useFormationControl } from '../../hooks/useFormationControl';
import { selectActiveVehicle } from '../../hooks/useFleet';
import { SHAPE_OPTIONS, FormationGlyph } from './FormationGlyphs';
import { TAC_GLASS, tacButton } from './tactical';

const MENU_WIDTH = 200;

function NumChip({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (n: number) => void }) {
  return (
    <label className="flex items-center gap-1 text-[9px] uppercase tracking-wide text-content-tertiary" data-tip={`${label} (m)`}>
      {label}
      <input
        type="number" min={min} max={max} value={value}
        onChange={(e) => onChange(Math.max(min, Math.min(max, Number(e.target.value))))}
        className="w-9 px-1 py-0.5 text-[10px] text-center rounded bg-surface-input border border-subtle text-content"
      />
    </label>
  );
}

export function FleetContextMenu(): JSX.Element | null {
  const menu = useFormationStore((s) => s.contextMenu);
  const close = useFormationStore((s) => s.closeContextMenu);
  const { canFollow, busy, leader, formations, shape, spacing, altStep, vehicles, setSpacing, setAltStep, formUp, releaseFromFormation } = useFormationControl();

  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  useLayoutEffect(() => {
    if (!menu) { setPos(null); return; }
    const h = ref.current?.offsetHeight ?? 220;
    const left = Math.min(menu.x, window.innerWidth - MENU_WIDTH - 8);
    const top = Math.min(menu.y, window.innerHeight - h - 8);
    setPos({ left: Math.max(8, left), top: Math.max(8, top) });
  }, [menu]);

  useEffect(() => {
    if (!menu) return;
    const onKey = (e: KeyboardEvent): void => { if (e.key === 'Escape') close(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [menu, close]);

  if (!menu) return null;
  const v = vehicles.find((x) => x.key === menu.vehicleKey);
  if (!v) return null;

  const group = formationOf(formations, v.key);
  const isLeader = group?.leaderKey === v.key;
  const isMember = group !== null;
  const isActive = leader?.key === v.key && !isMember;
  const run = (fn: () => void) => () => { fn(); close(); };
  const item = 'w-full px-2 py-1 text-left text-xs rounded text-content-secondary hover:bg-surface-raised hover:text-content transition-colors disabled:opacity-40';

  return createPortal(
    <>
      <div className="fixed inset-0 z-[2000]" onClick={() => close()} onContextMenu={(e) => { e.preventDefault(); close(); }} />
      <div
        ref={ref}
        className={`fixed z-[2001] py-1.5 px-1.5 rounded-lg select-none flex flex-col gap-1 ${TAC_GLASS}`}
        style={{ left: pos?.left ?? menu.x, top: pos?.top ?? menu.y, width: MENU_WIDTH, visibility: pos ? 'visible' : 'hidden' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-1.5 pb-1 text-[11px] font-mono font-semibold text-content border-b border-subtle">{v.label}</div>

        <button type="button" disabled={isActive} onClick={run(() => selectActiveVehicle(v.key, v.transportId))} className={item}>
          Command this vehicle
        </button>

        {canFollow && (
          <>
            <button type="button" disabled={busy || isLeader} onClick={run(() => { void formUp(undefined, v.key); })} className={item}>
              {isLeader ? 'Leading formation' : 'Set as leader'}
            </button>

            <div className="flex items-center justify-between gap-2 px-1.5 pt-1">
              <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-content-tertiary">Form up</span>
              <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                <NumChip label="gap" value={spacing} min={2} max={500} onChange={setSpacing} />
                <NumChip label="alt" value={altStep} min={0} max={100} onChange={setAltStep} />
              </div>
            </div>
            <div className="grid grid-cols-4 gap-1 px-0.5">
              {SHAPE_OPTIONS.map((o) => {
                const lit = isLeader && shape === o.value;
                return (
                  <button
                    key={o.value}
                    type="button"
                    disabled={busy}
                    onClick={run(() => { void formUp(o.value, v.key); })}
                    data-tip={o.label}
                    className={`grid place-items-center aspect-square rounded border transition-colors disabled:opacity-40 ${tacButton(lit)}`}
                  >
                    <FormationGlyph shape={o.value} size={20} />
                  </button>
                );
              })}
            </div>

            {isMember && (
              <button
                type="button"
                disabled={busy}
                onClick={run(() => { void releaseFromFormation(v.key); })}
                data-tip={isLeader ? 'Ends this formation - its wingmen return to manual control' : `Drop ${v.label} - the rest hold formation`}
                className="w-full mt-0.5 px-2 py-1 text-left text-xs rounded text-amber-500 hover:bg-amber-500/15 transition-colors disabled:opacity-40"
              >
                {isLeader ? 'Break this formation' : 'Leave formation'}
              </button>
            )}
          </>
        )}
      </div>
    </>,
    document.body,
  );
}
