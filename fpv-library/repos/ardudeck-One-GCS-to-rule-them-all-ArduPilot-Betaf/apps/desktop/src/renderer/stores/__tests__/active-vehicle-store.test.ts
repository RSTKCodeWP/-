import { describe, it, expect, beforeEach } from 'vitest';
import { useActiveVehicleStore, formationOf } from '../active-vehicle-store';
import type { VehicleInfoIpc } from '../../../shared/ipc-channels';

const vehicle = (key: string, transportId: string, sysid: number): VehicleInfoIpc => ({
  key,
  transportId,
  sysid,
  compid: 1,
  mavType: 2,
  boardId: null,
  boardUid: null,
  lastHeartbeatAt: 0,
  isActive: false,
});

const reset = () =>
  useActiveVehicleStore.setState({
    activeVehicleKey: null,
    activeTransportId: null,
    knownVehicles: {},
    selectedVehicleKeys: [],
    formations: {},
  });

describe('active-vehicle-store', () => {
  beforeEach(reset);

  it('auto-promotes the first discovered vehicle to active', () => {
    const v = vehicle('t1:1.1', 't1', 1);
    useActiveVehicleStore.getState().recordDiscovered(v);
    const s = useActiveVehicleStore.getState();
    expect(s.activeVehicleKey).toBe('t1:1.1');
    expect(s.activeTransportId).toBe('t1');
    expect(s.knownVehicles['t1:1.1']).toEqual(v);
  });

  it('does not re-promote when a second vehicle is discovered', () => {
    const store = useActiveVehicleStore.getState();
    store.recordDiscovered(vehicle('t1:1.1', 't1', 1));
    store.recordDiscovered(vehicle('t1:2.1', 't1', 2));
    const s = useActiveVehicleStore.getState();
    expect(s.activeVehicleKey).toBe('t1:1.1');
    expect(Object.keys(s.knownVehicles)).toHaveLength(2);
  });

  it('recordLost removes the vehicle and clears active when it was active', () => {
    const store = useActiveVehicleStore.getState();
    store.recordDiscovered(vehicle('t1:1.1', 't1', 1));
    store.recordLost('t1:1.1');
    const s = useActiveVehicleStore.getState();
    expect(s.activeVehicleKey).toBeNull();
    expect(s.activeTransportId).toBeNull();
    expect(s.knownVehicles['t1:1.1']).toBeUndefined();
  });

  it('recordLost keeps active pointer when a non-active vehicle is lost', () => {
    const store = useActiveVehicleStore.getState();
    store.recordDiscovered(vehicle('t1:1.1', 't1', 1)); // active
    store.recordDiscovered(vehicle('t1:2.1', 't1', 2));
    store.recordLost('t1:2.1');
    const s = useActiveVehicleStore.getState();
    expect(s.activeVehicleKey).toBe('t1:1.1');
    expect(s.knownVehicles['t1:2.1']).toBeUndefined();
  });

  it('setActive sets both transport and vehicle', () => {
    useActiveVehicleStore.getState().setActive('t2', 't2:3.1');
    const s = useActiveVehicleStore.getState();
    expect(s.activeTransportId).toBe('t2');
    expect(s.activeVehicleKey).toBe('t2:3.1');
  });

  it('hydrate replaces the known-vehicles map', () => {
    const store = useActiveVehicleStore.getState();
    store.recordDiscovered(vehicle('t1:1.1', 't1', 1));
    store.hydrate([vehicle('t9:5.1', 't9', 5), vehicle('t9:6.1', 't9', 6)]);
    const s = useActiveVehicleStore.getState();
    expect(Object.keys(s.knownVehicles).sort()).toEqual(['t9:5.1', 't9:6.1']);
    expect(s.knownVehicles['t1:1.1']).toBeUndefined();
  });

  it('clearAll empties everything', () => {
    const store = useActiveVehicleStore.getState();
    store.recordDiscovered(vehicle('t1:1.1', 't1', 1));
    store.clearAll();
    const s = useActiveVehicleStore.getState();
    expect(s.activeVehicleKey).toBeNull();
    expect(s.activeTransportId).toBeNull();
    expect(Object.keys(s.knownVehicles)).toHaveLength(0);
  });
});

describe('active-vehicle-store fleets', () => {
  beforeEach(reset);
  const f = () => useActiveVehicleStore.getState().formations;

  it('createFleet makes a leader-only fleet that persists', () => {
    useActiveVehicleStore.getState().createFleet('A');
    expect(f()).toEqual({ A: ['A'] });
  });

  it('createFleet is a no-op when the key already leads a fleet', () => {
    const s = useActiveVehicleStore.getState();
    s.createFleet('A');
    s.addToFleet('A', 'B');
    s.createFleet('A'); // must not wipe B
    expect(f()).toEqual({ A: ['A', 'B'] });
  });

  it('addToFleet appends a wingman and starts an active (2+) fleet', () => {
    const s = useActiveVehicleStore.getState();
    s.createFleet('A');
    s.addToFleet('A', 'B');
    expect(f()).toEqual({ A: ['A', 'B'] });
  });

  it('addToFleet moves a wingman between fleets, leaving the source intact', () => {
    const s = useActiveVehicleStore.getState();
    s.createFleet('A');
    s.addToFleet('A', 'B');
    s.addToFleet('A', 'C'); // A = [A,B,C]
    s.createFleet('D');
    s.addToFleet('D', 'C'); // C moves from A to D
    expect(f()).toEqual({ A: ['A', 'B'], D: ['D', 'C'] });
  });

  it('creating a second fleet leaves the first fleet fully intact (multi-leader bug)', () => {
    const s = useActiveVehicleStore.getState();
    // First fleet: A leads B, C, D
    s.createFleet('A');
    s.addToFleet('A', 'B');
    s.addToFleet('A', 'C');
    s.addToFleet('A', 'D');
    // Build a SECOND fleet led by wingman B, taking C
    s.createFleet('B'); // B peels out of A; A keeps [A, C, D]
    s.addToFleet('B', 'C'); // C moves to B; A keeps [A, D]
    const state = f();
    expect(state.A).toEqual(['A', 'D']);
    expect(state.B).toEqual(['B', 'C']);
    // The old fleet was NOT overwritten or dissolved.
    expect(formationOf(state, 'A')).toEqual({ leaderKey: 'A', memberKeys: ['A', 'D'] });
    expect(formationOf(state, 'C')).toEqual({ leaderKey: 'B', memberKeys: ['B', 'C'] });
  });

  it('removeFromFleet drops a wingman but keeps a leader-only fleet', () => {
    const s = useActiveVehicleStore.getState();
    s.createFleet('A');
    s.addToFleet('A', 'B');
    s.removeFromFleet('B');
    expect(f()).toEqual({ A: ['A'] });
  });

  it('removeFromFleet on the leader disbands the fleet, freeing wingmen', () => {
    const s = useActiveVehicleStore.getState();
    s.createFleet('A');
    s.addToFleet('A', 'B');
    s.removeFromFleet('A');
    expect(f()).toEqual({});
    expect(formationOf(useActiveVehicleStore.getState().formations, 'B')).toBeNull();
  });

  it('recordLost keeps a fleet as leader-only when a wingman is lost', () => {
    const s = useActiveVehicleStore.getState();
    s.recordDiscovered(vehicle('A', 'tA', 1));
    s.recordDiscovered(vehicle('B', 'tB', 2));
    s.createFleet('A');
    s.addToFleet('A', 'B');
    s.recordLost('B');
    expect(f()).toEqual({ A: ['A'] });
  });

  it('recordLost disbands a fleet when its leader is lost', () => {
    const s = useActiveVehicleStore.getState();
    s.recordDiscovered(vehicle('A', 'tA', 1));
    s.recordDiscovered(vehicle('B', 'tB', 2));
    s.createFleet('A');
    s.addToFleet('A', 'B');
    s.recordLost('A');
    expect(f()).toEqual({});
  });
});
