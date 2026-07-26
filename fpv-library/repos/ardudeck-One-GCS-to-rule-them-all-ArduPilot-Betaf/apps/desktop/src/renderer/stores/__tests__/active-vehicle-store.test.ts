import { describe, it, expect, beforeEach } from 'vitest';
import { useActiveVehicleStore } from '../active-vehicle-store';
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
