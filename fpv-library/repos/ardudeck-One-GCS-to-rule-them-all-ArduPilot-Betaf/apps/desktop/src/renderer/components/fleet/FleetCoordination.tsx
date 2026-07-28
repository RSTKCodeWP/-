/**
 * Fleet-wide + per-fleet group actions. "Take off all" lifts every connected vehicle;
 * each active fleet then gets its own row: a shape selector (change that fleet's
 * formation), a "Take off" that lifts only that fleet, and "Start mission" for its
 * leader. Per-vehicle formation membership (create leader, add to fleet, disband) lives
 * in the right-click menu. Renders nothing for a single vehicle, or when the connected
 * engine advertises no group actions.
 */

import { useState } from 'react';
import { useFormationControl } from '../../hooks/useFormationControl';
import { useFleetUiStore, isFleetExpanded } from '../../stores/fleet-ui-store';
import { SHAPE_OPTIONS, FormationGlyph } from './FormationGlyphs';
import { FleetChevron, FleetCountHeader } from './FleetDisclosure';
import { tacButton } from './tactical';

export function FleetCoordination() {
  const { hasServer, vehicles, canTakeoff, canFollow, formations, shape, spacing, altStep, busy, takeOffAll, takeOffFleet, startLeaderMission, reshapeFleet } = useFormationControl();
  const uiOverrides = useFleetUiStore((s) => s.overrides);
  const toggleFleet = useFleetUiStore((s) => s.toggle);
  const [alt, setAlt] = useState(10);

  if (!hasServer || vehicles.length === 0) return null;
  if (!canTakeoff && !canFollow) return null;

  const groups = Object.entries(formations)
    .map(([leaderKey, memberKeys]) => ({
      leader: vehicles.find((v) => v.key === leaderKey),
      wingmen: memberKeys.length - 1,
    }))
    .filter((g): g is { leader: NonNullable<typeof g.leader>; wingmen: number } => !!g.leader)
    .sort((a, b) => a.leader.sysid - b.leader.sysid);
  const leaderKeys = groups.map((g) => g.leader.key);

  const takeoffBtn = 'flex-1 px-2 py-1.5 text-[11px] font-medium rounded border border-cyan-500/30 bg-cyan-500/10 text-content hover:bg-cyan-500/20 transition-colors disabled:opacity-50';
  const subtleBtn = 'flex-1 px-2 py-1.5 text-[11px] font-medium rounded border border-subtle bg-surface text-content-secondary hover:bg-surface-raised hover:text-content transition-colors disabled:opacity-50';

  return (
    <div className="border-t border-subtle px-2 py-2 flex flex-col gap-2">
      {canTakeoff && (
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => takeOffAll(alt)}
            disabled={busy}
            data-tip={`Every connected vehicle arms and climbs to ${alt} m together`}
            className={takeoffBtn}
          >
            Take off all
          </button>
          <label className="flex items-center gap-1 text-[9px] uppercase tracking-wide text-content-tertiary" data-tip="Takeoff altitude (m)">
            alt
            <input
              type="number" min={1} max={120} value={alt}
              onChange={(e) => setAlt(Math.max(1, Math.min(120, Number(e.target.value) || 1)))}
              className="w-11 px-1 py-1 text-[11px] text-center rounded bg-surface-input border border-subtle text-content"
            />
          </label>
        </div>
      )}

      <FleetCountHeader leaderKeys={leaderKeys} className="px-0.5" />

      {groups.map((g) => {
        const expanded = isFleetExpanded(uiOverrides, g.leader.key, leaderKeys.length);
        return (
          <div key={g.leader.key} className="rounded-md border border-subtle bg-surface p-1.5 flex flex-col gap-1.5">
            {/* One-line fleet header: chevron, label +N, quick take off. */}
            <div className="flex items-center gap-1.5 text-[10px]">
              <button
                type="button"
                onClick={() => toggleFleet(g.leader.key, expanded)}
                className="shrink-0 w-4 grid place-items-center text-content-tertiary hover:text-content"
                data-tip={expanded ? 'Collapse fleet' : 'Expand fleet'}
              >
                <FleetChevron open={expanded} />
              </button>
              <span className="font-semibold uppercase tracking-[0.12em] text-cyan-500/90">Fleet</span>
              <span className="font-mono text-content-secondary truncate flex-1">{g.leader.label} +{g.wingmen}</span>
              <span className="font-mono text-content-tertiary truncate max-w-[64px]" data-tip={`${g.leader.label} mode`}>{g.leader.mode}</span>
              {canTakeoff && (
                <button
                  onClick={() => { void takeOffFleet(g.leader.key, alt); }}
                  disabled={busy}
                  data-tip={`Arm and climb only ${g.leader.label}'s fleet to ${alt} m`}
                  className="shrink-0 px-2 py-1 text-[10px] font-medium rounded border border-cyan-500/30 bg-cyan-500/10 text-content hover:bg-cyan-500/20 transition-colors disabled:opacity-50"
                >
                  Take off
                </button>
              )}
            </div>

            {expanded && (
              <>
                {/* Shape selector - only meaningful once the fleet has wingmen to arrange. */}
                {canFollow && g.wingmen > 0 && (
                  <div className="grid grid-cols-4 gap-1">
                    {SHAPE_OPTIONS.map((o) => {
                      const lit = shape === o.value;
                      return (
                        <button
                          key={o.value}
                          type="button"
                          disabled={busy || lit}
                          onClick={() => { void reshapeFleet(g.leader.key, o.value); }}
                          data-tip={`Re-form ${g.leader.label}'s fleet: ${o.label}`}
                          className={`grid place-items-center aspect-square rounded border transition-colors disabled:opacity-60 ${tacButton(lit)}`}
                        >
                          <FormationGlyph shape={o.value} size={18} />
                        </button>
                      );
                    })}
                  </div>
                )}
                <button
                  onClick={() => { void startLeaderMission(g.leader.key); }}
                  disabled={busy}
                  data-tip={`${g.leader.label} flies its uploaded mission in AUTO; its wingmen hold formation and follow`}
                  className={subtleBtn}
                >
                  Start mission
                </button>
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
