/**
 * Shared fleet-formation commands, used by both the rail glyph bar (FleetCoordination)
 * and the right-click menu (FleetContextMenu). Encapsulates orchestration-server
 * discovery, capability gating and the intent calls so the two surfaces stay in lock
 * step. Every action is one call - pick a glyph, the fleet forms up; no apply step.
 *
 * Several formations can run at once (the engine keeps one follow loop per leader).
 * The desktop mirror lives in active-vehicle-store.formations; a vehicle belongs to
 * at most one fleet. Fleets are built explicitly - createFleet makes a leader-only
 * "empty fleet" that commands nothing until addToFleet gives it a wingman. Because
 * the engine won't release a dropped vehicle from a merely-shrunk follow.leader, any
 * op that removes a vehicle from a fleet (move, peel, remove) stops that fleet's loop
 * and reforms the remainder; adds just re-issue follow.leader, which supersedes.
 *
 * Geometry (shape / spacing / alt-step) is PER FLEET - see formation-store. Every
 * follow.leader issued here reads the geometry of the fleet it is commanding, so
 * reshaping one fleet can never leak into another's next re-issue.
 */

import { useOrchestrationStore } from '../stores/orchestration-store';
import { useActiveVehicleStore, formationOf } from '../stores/active-vehicle-store';
import { useMissionStore } from '../stores/mission-store';
import { useFormationStore, formationConfigOf, type FleetFormationConfig } from '../stores/formation-store';
import { SHAPE_BY_VALUE } from '../components/fleet/FormationGlyphs';
import { useFleetVehicles, selectActiveVehicle, type FleetVehicle } from './useFleet';

export interface FormationControl {
  /** True when an orchestration engine is connected. */
  hasServer: boolean;
  vehicles: FleetVehicle[];
  canTakeoff: boolean;
  canFollow: boolean;
  /** At least one formation is currently active. */
  forming: boolean;
  /** Active formations: leader key -> member keys (leader first). */
  formations: Record<string, string[]>;
  /** The default leader for a NEW formation (the selected vehicle, else first). */
  leader: FleetVehicle | undefined;
  /**
   * A fleet's live geometry, by leader key. Pass null/undefined (or a key that leads no
   * fleet) for the seed applied to the next fleet formed. Per fleet, so one fleet's
   * glyph bar never reflects or overwrites another's shape.
   */
  configFor: (leaderKey?: string | null) => FleetFormationConfig;
  busy: boolean;
  /** Patch a fleet's geometry, or the defaults when leaderKey is null. */
  setConfig: (leaderKey: string | null, patch: Partial<FleetFormationConfig>) => void;
  /** Form up / re-form a group on a leader. Optional shape and leader overrides. */
  formUp: (shapeValue?: string, leaderKeyOverride?: string) => Promise<void>;
  /** Re-form ONE existing fleet with a new shape, touching only its current members. */
  reshapeFleet: (leaderKey: string, shapeValue: string) => Promise<void>;
  /** Create a leader-only fleet ("empty fleet"); no follow loop until it gets a wingman. */
  createFleet: (leaderKey: string) => Promise<void>;
  /** Add a vehicle to a fleet, moving it out of any fleet it was in, and (re)form loops. */
  addToFleet: (leaderKey: string, memberKey: string) => Promise<void>;
  /** Drop a vehicle from its fleet; the leader disbands it, a wingman just leaves. */
  removeFromFleet: (memberKey: string) => Promise<void>;
  /** Disband a whole fleet (alias for breakFormation on a leader). */
  disbandFleet: (leaderKey: string) => Promise<void>;
  /** Break one formation (by leader key), or every formation when omitted. */
  breakFormation: (leaderKey?: string) => Promise<void>;
  /** Drop a single vehicle from its formation (leader/last -> that group breaks). */
  releaseFromFormation: (key: string) => Promise<void>;
  takeOffAll: (altitude: number) => Promise<void>;
  /** Take off just one fleet (its leader + wingmen), leaving other fleets grounded. */
  takeOffFleet: (leaderKey: string, altitude: number) => Promise<void>;
  /** Start one formation leader's mission (AUTO); wingmen keep following. */
  startLeaderMission: (leaderKey: string) => Promise<void>;
}

export function useFormationControl(): FormationControl {
  const servers = useOrchestrationStore((s) => s.servers);
  const activeKey = useActiveVehicleStore((s) => s.activeVehicleKey);
  const formations = useActiveVehicleStore((s) => s.formations);
  const setFormation = useActiveVehicleStore((s) => s.setFormation);
  const removeFormation = useActiveVehicleStore((s) => s.removeFormation);
  const clearFormations = useActiveVehicleStore((s) => s.clearFormations);
  const vehicles = useFleetVehicles();
  const defaults = useFormationStore((s) => s.defaults);
  const byFleet = useFormationStore((s) => s.byFleet);
  const setConfig = useFormationStore((s) => s.setConfig);
  const dropConfig = useFormationStore((s) => s.dropConfig);
  const clearConfigs = useFormationStore((s) => s.clearConfigs);
  const busy = useFormationStore((s) => s.busy);
  const setBusy = useFormationStore((s) => s.setBusy);

  const configFor = (leaderKey?: string | null): FleetFormationConfig =>
    formationConfigOf(byFleet, defaults, leaderKey);
  // Reads the store directly so an action that just wrote a config sees it, rather than
  // the render-time snapshot closed over above.
  const liveConfig = (leaderKey: string): FleetFormationConfig => {
    const s = useFormationStore.getState();
    return formationConfigOf(s.byFleet, s.defaults, leaderKey);
  };

  // Prefer an engine that advertises capabilities; fall back to any connected one so a
  // stale build with empty caps doesn't hide the actions (our orchestrator always
  // supports these intents).
  const server = Object.values(servers).find((s) => s.capabilities.length > 0) ?? Object.values(servers)[0];
  const caps = server
    ? (server.capabilities.length > 0 ? server.capabilities : ['takeoff.synchronized', 'follow.leader', 'formation.stop'])
    : [];
  const canTakeoff = caps.includes('takeoff.synchronized');
  const canFollow = caps.includes('follow.leader') && vehicles.length >= 2;
  const forming = Object.keys(formations).length > 0;

  const leader = vehicles.find((v) => v.key === activeKey) ?? vehicles[0];

  const submit = async (kind: string, sysids: number[] | undefined, payload: unknown): Promise<void> => {
    if (!server) return;
    setBusy(true);
    try {
      await window.electronAPI?.submitIntent?.(server.transportId, { kind, vehicleSysids: sysids, payload });
    } finally {
      setBusy(false);
    }
  };

  const formUp = async (shapeValue?: string, leaderKeyOverride?: string): Promise<void> => {
    const target = vehicles.find((v) => v.key === (leaderKeyOverride ?? leader?.key));
    if (!target) return;
    // Geometry belongs to THIS fleet: an explicit shape is written to its config (with
    // the shape's preset spacing, if any), otherwise it keeps what it already had, or
    // inherits the defaults on a first form-up.
    if (shapeValue) {
      const preset = SHAPE_BY_VALUE.get(shapeValue)?.spacing;
      setConfig(target.key, preset ? { shape: shapeValue, spacing: preset } : { shape: shapeValue });
    }
    const cfg = liveConfig(target.key);
    // Followers, in priority order:
    //  1. explicit checkbox selection, when any are checked;
    //  2. the target's own current wingmen, when it already leads a fleet (this is a
    //     re-form / apply-shape, not a new grab);
    //  3. otherwise only FREE vehicles, so forming up never steals another fleet's
    //     members. Building a second fleet from an in-fleet drone goes through
    //     createFleet / addToFleet instead.
    const selected = useActiveVehicleStore.getState().selectedVehicleKeys;
    const checkedWingmen = vehicles.filter((v) => v.key !== target.key && selected.includes(v.key));
    const targetGroup = formationOf(formations, target.key);
    const ownWingmen = targetGroup?.leaderKey === target.key
      ? vehicles.filter((v) => v.key !== target.key && targetGroup.memberKeys.includes(v.key))
      : [];
    const free = vehicles.filter((v) => v.key !== target.key && formationOf(formations, v.key) === null);
    const followers = checkedWingmen.length > 0 ? checkedWingmen : ownWingmen.length > 0 ? ownWingmen : free;
    if (followers.length === 0) return;
    const ordered = [target.sysid, ...followers.map((v) => v.sysid)];
    await submit('follow.leader', ordered, { spacingM: cfg.spacing, altStepM: cfg.altStep, shape: cfg.shape });
    setFormation(target.key, [target.key, ...followers.map((v) => v.key)]);
    // CRITICAL: command the leader now, else map/flight commands still target whatever
    // wingman was selected, the follow loop overrides them, and "nothing moves".
    selectActiveVehicle(target.key, target.transportId);
  };

  const sysidsFor = (keys: string[]): number[] =>
    keys.map((k) => vehicles.find((v) => v.key === k)?.sysid).filter((n): n is number => n != null);

  // Re-form ONE fleet with a new shape. Reads that fleet's current members and re-issues
  // its follow.leader with the new geometry - no membership change, no free/selection grab,
  // so other fleets are never touched. (formUp is for building/grabbing; this is not.)
  const reshapeFleet = async (leaderKey: string, shapeValue: string): Promise<void> => {
    const members = useActiveVehicleStore.getState().formations[leaderKey];
    if (!members || members.length < 2) return;
    const preset = SHAPE_BY_VALUE.get(shapeValue)?.spacing;
    setConfig(leaderKey, preset ? { shape: shapeValue, spacing: preset } : { shape: shapeValue });
    const cfg = liveConfig(leaderKey);
    await submit('follow.leader', sysidsFor(members), { spacingM: cfg.spacing, altStepM: cfg.altStep, shape: cfg.shape });
  };

  // (Re)issue the follow loop for a fleet that GAINED a member or changed shape. The
  // engine supersedes any prior loop for this leader (they share members), so no stop
  // is needed. A leader-only fleet (< 2 members) commands nothing.
  const pushFleet = async (leaderKey: string): Promise<void> => {
    const members = useActiveVehicleStore.getState().formations[leaderKey];
    if (!members || members.length < 2) return;
    const cfg = liveConfig(leaderKey);
    await submit('follow.leader', sysidsFor(members), { spacingM: cfg.spacing, altStepM: cfg.altStep, shape: cfg.shape });
  };

  // Reconcile a fleet that LOST a member: stop its loop first (the engine won't drop a
  // released vehicle from a merely-shrunk follow.leader), then reform the remainder.
  const reformFleet = async (leaderKey: string): Promise<void> => {
    const leaderV = vehicles.find((v) => v.key === leaderKey);
    await submit('formation.stop', leaderV ? [leaderV.sysid] : undefined, null);
    await pushFleet(leaderKey);
  };

  const createFleet = async (leaderKey: string): Promise<void> => {
    const src = formationOf(useActiveVehicleStore.getState().formations, leaderKey);
    if (src && src.leaderKey === leaderKey) return; // already leads a fleet
    useActiveVehicleStore.getState().createFleet(leaderKey);
    // If it peeled out of another fleet as a wingman, that fleet must release it.
    if (src) await reformFleet(src.leaderKey);
  };

  const addToFleet = async (leaderKey: string, memberKey: string): Promise<void> => {
    if (memberKey === leaderKey) return;
    const src = formationOf(useActiveVehicleStore.getState().formations, memberKey);
    if (src && src.leaderKey === memberKey) {
      // Moving a leader into another fleet dissolves its old fleet; stop that loop and
      // forget its geometry so a future fleet on this key starts from the defaults.
      const oldLeaderV = vehicles.find((v) => v.key === memberKey);
      await submit('formation.stop', oldLeaderV ? [oldLeaderV.sysid] : undefined, null);
      dropConfig(memberKey);
    }
    useActiveVehicleStore.getState().addToFleet(leaderKey, memberKey);
    await pushFleet(leaderKey); // dest gains the member (also aborts src loop, shared)
    if (src && src.leaderKey !== leaderKey && src.leaderKey !== memberKey) {
      await reformFleet(src.leaderKey); // restart the source fleet without the moved vehicle
    }
    const leaderV = vehicles.find((v) => v.key === leaderKey);
    if (leaderV) selectActiveVehicle(leaderV.key, leaderV.transportId);
  };

  const removeFromFleet = async (memberKey: string): Promise<void> => {
    const grp = formationOf(useActiveVehicleStore.getState().formations, memberKey);
    if (!grp) return;
    useActiveVehicleStore.getState().removeFromFleet(memberKey);
    if (grp.leaderKey === memberKey) {
      const leaderV = vehicles.find((v) => v.key === memberKey);
      await submit('formation.stop', leaderV ? [leaderV.sysid] : undefined, null);
      dropConfig(memberKey);
    } else {
      await reformFleet(grp.leaderKey);
    }
  };

  const disbandFleet = (leaderKey: string): Promise<void> => breakFormation(leaderKey);

  const breakFormation = async (leaderKey?: string): Promise<void> => {
    if (leaderKey) {
      const leaderV = vehicles.find((v) => v.key === leaderKey);
      // Scoped stop: the engine drops only the formation(s) containing this sysid.
      await submit('formation.stop', leaderV ? [leaderV.sysid] : undefined, null);
      removeFormation(leaderKey);
      dropConfig(leaderKey);
    } else {
      await submit('formation.stop', undefined, null);
      clearFormations();
      clearConfigs();
    }
  };

  // Drop ONE vehicle from its formation, leaving the rest in formation. Releasing the
  // leader (or the last wingman) ends that group; releasing a wingman re-forms the
  // remaining vehicles without it, so the orchestrator stops commanding it.
  const releaseFromFormation = async (key: string): Promise<void> => {
    const group = formationOf(formations, key);
    if (!group) return;
    const leaderV = vehicles.find((v) => v.key === group.leaderKey);
    const remaining = vehicles.filter((v) => group.memberKeys.includes(v.key) && v.key !== key && v.key !== group.leaderKey);
    if (key === group.leaderKey || !leaderV || remaining.length === 0) {
      await breakFormation(group.leaderKey);
      return;
    }
    // Stop THIS group's follow loop first (releases every vehicle in it, including the
    // one leaving), then re-form only the remaining ones - simply omitting a vehicle
    // from a re-issued follow.leader doesn't make the orchestrator let it go.
    await submit('formation.stop', [leaderV.sysid], null);
    const ordered = [leaderV.sysid, ...remaining.map((v) => v.sysid)];
    const cfg = liveConfig(leaderV.key);
    await submit('follow.leader', ordered, { spacingM: cfg.spacing, altStepM: cfg.altStep, shape: cfg.shape });
    setFormation(leaderV.key, [leaderV.key, ...remaining.map((v) => v.key)]);
    selectActiveVehicle(leaderV.key, leaderV.transportId);
  };

  const takeOffAll = (altitude: number): Promise<void> =>
    submit('takeoff.synchronized', vehicles.map((v) => v.sysid), { altitude });

  const takeOffFleet = (leaderKey: string, altitude: number): Promise<void> => {
    const members = useActiveVehicleStore.getState().formations[leaderKey] ?? [leaderKey];
    return submit('takeoff.synchronized', sysidsFor(members), { altitude });
  };

  // Start ONLY this leader's mission (AUTO); its wingmen stay in GUIDED and the follow
  // loop keeps formation. (Re)upload the leader's assigned WP group first so the
  // operator never has to remember a separate upload step.
  const startLeaderMission = async (leaderKey: string): Promise<void> => {
    const leaderV = vehicles.find((v) => v.key === leaderKey);
    if (!leaderV) return;
    setBusy(true);
    try {
      const ms = useMissionStore.getState();
      const grp = ms.groups.find((g) => g.assignedVehicleKey === leaderV.key);
      if (grp) {
        const uploaded = await ms.uploadGroupToVehicle(grp.id, leaderV.key);
        if (!uploaded) return;
      }
      await window.electronAPI?.vehicleCommand?.(leaderV.key, { kind: 'mission-start' });
    } finally {
      setBusy(false);
    }
  };

  return {
    hasServer: !!server,
    vehicles,
    canTakeoff,
    canFollow,
    forming,
    formations,
    leader,
    configFor,
    busy,
    setConfig,
    formUp,
    reshapeFleet,
    createFleet,
    addToFleet,
    removeFromFleet,
    disbandFleet,
    breakFormation,
    releaseFromFormation,
    takeOffAll,
    takeOffFleet,
    startLeaderMission,
  };
}
