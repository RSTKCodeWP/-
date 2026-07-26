/**
 * Fleet-wide actions for the rail - the genuinely *group* commands that aren't tied to
 * one vehicle: synchronized take-off and starting each formation leader's mission.
 * Per-vehicle formation orders (set leader, pick a shape, break) live in the right-click
 * menu (FleetContextMenu) instead, so there's a single place to do them. Every active
 * formation shows a compact status line with its own mission trigger. Renders nothing
 * for a single vehicle, or when the connected engine advertises no group actions.
 */

import { useState } from 'react';
import { useFormationControl } from '../../hooks/useFormationControl';
import { SHAPE_BY_VALUE } from './FormationGlyphs';

export function FleetCoordination() {
  const { hasServer, vehicles, canTakeoff, canFollow, formations, shape, spacing, altStep, busy, takeOffAll, startLeaderMission } = useFormationControl();
  const [alt, setAlt] = useState(10);

  if (!hasServer || vehicles.length === 0) return null;
  if (!canTakeoff && !canFollow) return null;

  const shapeLabel = SHAPE_BY_VALUE.get(shape)?.label ?? shape;
  const groups = Object.entries(formations)
    .map(([leaderKey, memberKeys]) => ({
      leader: vehicles.find((v) => v.key === leaderKey),
      count: memberKeys.length - 1,
    }))
    .filter((g): g is { leader: NonNullable<typeof g.leader>; count: number } => !!g.leader);

  return (
    <div className="border-t border-subtle px-2 py-2 flex flex-col gap-1.5">
      {groups.map((g) => (
        <div key={g.leader.key} className="flex items-center gap-1.5 text-[10px]">
          <span className="font-semibold uppercase tracking-[0.12em] text-cyan-500/90">Formation</span>
          <span className="font-mono text-content-secondary truncate">{shapeLabel} · {g.leader.label} +{g.count} · {spacing}·{altStep}m</span>
        </div>
      ))}

      {canTakeoff && (
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => takeOffAll(alt)}
            disabled={busy}
            data-tip={`Each vehicle arms and climbs to ${alt} m together`}
            className="flex-1 px-2 py-1.5 text-[11px] font-medium rounded border border-cyan-500/30 bg-cyan-500/10 text-content hover:bg-cyan-500/20 transition-colors disabled:opacity-50"
          >
            Take off all
          </button>
          <input
            type="number" min={1} max={120} value={alt}
            onChange={(e) => setAlt(Math.max(1, Math.min(120, Number(e.target.value))))}
            data-tip="Takeoff altitude (m)"
            className="w-11 shrink-0 px-1 py-1 text-[11px] text-center rounded bg-surface-input border border-subtle text-content"
          />
        </div>
      )}

      {groups.map((g) => (
        <button
          key={g.leader.key}
          onClick={() => { void startLeaderMission(g.leader.key); }}
          disabled={busy}
          data-tip={`${g.leader.label} flies its uploaded mission in AUTO; its wingmen hold formation and follow`}
          className="w-full px-2 py-1.5 text-[11px] font-medium rounded border border-subtle bg-surface text-content-secondary hover:bg-surface-raised hover:text-content transition-colors disabled:opacity-50"
        >
          Start {g.leader.label} mission
        </button>
      ))}
    </div>
  );
}
