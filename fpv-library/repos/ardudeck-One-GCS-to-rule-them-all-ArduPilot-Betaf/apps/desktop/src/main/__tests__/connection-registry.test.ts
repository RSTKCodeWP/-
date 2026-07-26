import { describe, it, expect, beforeEach } from 'vitest';
import type { Transport } from '@ardudeck/comms';
import type { MAVLinkParser } from '@ardudeck/mavlink-ts';
import { ConnectionRegistry } from '../connection/connection-registry.js';
import { makeVehicleKey, type TransportConfig } from '../connection/types.js';

/**
 * Smoke tests for the ConnectionRegistry.
 *
 * The registry is a pure data structure - no IPC, no transport lifecycle. These
 * tests cover the contract the ipc-handlers.ts integration relies on:
 *   - register / unregister bookkeeping
 *   - vehicle discovery via recordHeartbeat
 *   - active selection guards
 *   - compatibility shims (getActiveTransport, getActiveMavlinkParser, getActiveVehicleType)
 */

// Minimal stand-ins. The registry only stores these by reference; it never calls
// anything on them, so plain objects with the right shape are enough.
const fakeTransport = (portName = 'fake'): Transport => ({ portName } as unknown as Transport);
const fakeParser = (): MAVLinkParser => ({} as unknown as MAVLinkParser);
const fakeConfig: TransportConfig = { type: 'udp', udpPort: 14550, udpMode: 'listen' };

describe('ConnectionRegistry', () => {
  let registry: ConnectionRegistry;

  beforeEach(() => {
    registry = new ConnectionRegistry();
  });

  describe('register / unregister', () => {
    it('returns a stable, unique transportId from register', () => {
      const a = registry.register(fakeTransport('a'), fakeParser(), fakeConfig);
      const b = registry.register(fakeTransport('b'), fakeParser(), fakeConfig);
      expect(a).not.toBe(b);
      expect(registry.transportCount()).toBe(2);
    });

    it('getTransport returns the entry by id', () => {
      const transport = fakeTransport('a');
      const id = registry.register(transport, fakeParser(), fakeConfig);
      const entry = registry.getTransport(id);
      expect(entry?.id).toBe(id);
      expect(entry?.transport).toBe(transport);
    });

    it('listTransports returns all entries in insertion order', () => {
      const a = registry.register(fakeTransport('a'), fakeParser(), fakeConfig);
      const b = registry.register(fakeTransport('b'), fakeParser(), fakeConfig);
      expect(registry.listTransports().map(t => t.id)).toEqual([a, b]);
    });

    it('unregister removes the entry and is silent on unknown ids', () => {
      const id = registry.register(fakeTransport(), fakeParser(), fakeConfig);
      registry.unregister(id);
      expect(registry.getTransport(id)).toBeUndefined();
      expect(() => registry.unregister('does-not-exist')).not.toThrow();
    });

    it('unregister clears active selection if the active transport is removed', () => {
      const id = registry.register(fakeTransport(), fakeParser(), fakeConfig);
      registry.recordHeartbeat(id, 1, 1, 2);
      registry.setActive(id, makeVehicleKey(id, 1, 1));
      registry.unregister(id);
      expect(registry.getActiveTransportId()).toBeNull();
      expect(registry.getActiveVehicleKey()).toBeNull();
    });

    it('clear empties the registry and active selection', () => {
      const id = registry.register(fakeTransport(), fakeParser(), fakeConfig);
      registry.recordHeartbeat(id, 1, 1, 2);
      registry.setActive(id, makeVehicleKey(id, 1, 1));
      registry.clear();
      expect(registry.transportCount()).toBe(0);
      expect(registry.getActiveTransportId()).toBeNull();
    });
  });

  describe('vehicle discovery', () => {
    it('recordHeartbeat creates a new vehicle on first sighting', () => {
      const id = registry.register(fakeTransport(), fakeParser(), fakeConfig);
      const result = registry.recordHeartbeat(id, 1, 1, 2);
      expect(result?.isNew).toBe(true);
      expect(result?.vehicle.sysid).toBe(1);
      expect(result?.vehicle.compid).toBe(1);
      expect(result?.vehicle.mavType).toBe(2);
      expect(result?.vehicle.key).toBe(makeVehicleKey(id, 1, 1));
    });

    it('recordHeartbeat returns isNew=false on subsequent heartbeats', () => {
      const id = registry.register(fakeTransport(), fakeParser(), fakeConfig);
      registry.recordHeartbeat(id, 1, 1, 2);
      const result = registry.recordHeartbeat(id, 1, 1, 2);
      expect(result?.isNew).toBe(false);
    });

    it('recordHeartbeat updates mavType and lastHeartbeatAt on rediscovery', () => {
      const id = registry.register(fakeTransport(), fakeParser(), fakeConfig);
      registry.recordHeartbeat(id, 1, 1, 2);
      const before = registry.getVehicle(id, 1, 1)!.lastHeartbeatAt;
      registry.recordHeartbeat(id, 1, 1, 13);
      const after = registry.getVehicle(id, 1, 1)!;
      expect(after.mavType).toBe(13);
      expect(after.lastHeartbeatAt).toBeGreaterThanOrEqual(before);
    });

    it('recordHeartbeat returns null for unknown transport', () => {
      const result = registry.recordHeartbeat('nope', 1, 1, 2);
      expect(result).toBeNull();
    });

    it('distinct (sysid, compid) tuples create distinct vehicles on the same transport', () => {
      const id = registry.register(fakeTransport(), fakeParser(), fakeConfig);
      registry.recordHeartbeat(id, 1, 1, 2);
      registry.recordHeartbeat(id, 1, 191, 2);
      registry.recordHeartbeat(id, 2, 1, 2);
      expect(registry.listVehicles()).toHaveLength(3);
    });

    it('overlapping sysids on different transports produce distinct vehicle keys', () => {
      const a = registry.register(fakeTransport('a'), fakeParser(), fakeConfig);
      const b = registry.register(fakeTransport('b'), fakeParser(), fakeConfig);
      const va = registry.recordHeartbeat(a, 1, 1, 2)!.vehicle;
      const vb = registry.recordHeartbeat(b, 1, 1, 2)!.vehicle;
      expect(va.key).not.toBe(vb.key);
      expect(registry.listVehicles()).toHaveLength(2);
    });

    it('tracker (sysid 9) and vehicle (sysid 1) on one transport coexist as distinct vehicles', () => {
      const id = registry.register(fakeTransport(), fakeParser(), fakeConfig);
      registry.recordHeartbeat(id, 1, 1, 2); // copter
      registry.recordHeartbeat(id, 9, 1, 5); // antenna tracker
      const vehicle = registry.getVehicle(id, 1, 1)!;
      const tracker = registry.getVehicle(id, 9, 1)!;
      expect(vehicle.mavType).toBe(2);
      expect(tracker.mavType).toBe(5);
      expect(registry.listVehicles()).toHaveLength(2);
    });

    it('updateVehicle patches mutable fields and ignores unknown keys', () => {
      const id = registry.register(fakeTransport(), fakeParser(), fakeConfig);
      const { vehicle } = registry.recordHeartbeat(id, 1, 1, 2)!;
      registry.updateVehicle(vehicle.key, { boardId: 'Pixhawk6C', boardUid: 'abc' });
      const after = registry.getVehicleByKey(vehicle.key)!;
      expect(after.boardId).toBe('Pixhawk6C');
      expect(after.boardUid).toBe('abc');
      expect(() => registry.updateVehicle('does-not-exist', { boardId: 'CubeOrange' })).not.toThrow();
    });

    it('getVehicleByKey returns undefined for malformed keys', () => {
      expect(registry.getVehicleByKey('no-colon-here')).toBeUndefined();
    });
  });

  describe('active selection', () => {
    it('starts with no active selection', () => {
      expect(registry.getActive()).toBeNull();
      expect(registry.getActiveTransportId()).toBeNull();
      expect(registry.getActiveVehicleKey()).toBeNull();
    });

    it('setActive(null) clears the selection', () => {
      const id = registry.register(fakeTransport(), fakeParser(), fakeConfig);
      registry.recordHeartbeat(id, 1, 1, 2);
      registry.setActive(id, makeVehicleKey(id, 1, 1));
      registry.setActive(null);
      expect(registry.getActive()).toBeNull();
    });

    it('setActive throws on unknown transportId', () => {
      expect(() => registry.setActive('nope')).toThrow(/unknown transportId/);
    });

    it('setActive throws on vehicleKey not belonging to the transport', () => {
      const a = registry.register(fakeTransport('a'), fakeParser(), fakeConfig);
      const b = registry.register(fakeTransport('b'), fakeParser(), fakeConfig);
      registry.recordHeartbeat(b, 1, 1, 2);
      expect(() => registry.setActive(a, makeVehicleKey(b, 1, 1))).toThrow(/does not belong/);
    });

    it('getActive returns the selected transport and vehicle together', () => {
      const id = registry.register(fakeTransport(), fakeParser(), fakeConfig);
      registry.recordHeartbeat(id, 1, 1, 2);
      const key = makeVehicleKey(id, 1, 1);
      registry.setActive(id, key);
      const active = registry.getActive();
      expect(active?.transport.id).toBe(id);
      expect(active?.vehicle.key).toBe(key);
    });
  });

  describe('compatibility shims', () => {
    it('getActiveTransport returns null when no transport is active', () => {
      expect(registry.getActiveTransport()).toBeNull();
    });

    it('getActiveTransport returns the underlying Transport instance when active', () => {
      const transport = fakeTransport('compat');
      const id = registry.register(transport, fakeParser(), fakeConfig);
      registry.recordHeartbeat(id, 1, 1, 2);
      registry.setActive(id, makeVehicleKey(id, 1, 1));
      expect(registry.getActiveTransport()).toBe(transport);
    });

    it('getActiveMavlinkParser returns the per-transport parser', () => {
      const parser = fakeParser();
      const id = registry.register(fakeTransport(), parser, fakeConfig);
      registry.recordHeartbeat(id, 1, 1, 2);
      registry.setActive(id, makeVehicleKey(id, 1, 1));
      expect(registry.getActiveMavlinkParser()).toBe(parser);
    });

    it('getActiveVehicleType returns 0 when no vehicle is active (legacy default)', () => {
      expect(registry.getActiveVehicleType()).toBe(0);
    });

    it('getActiveVehicleType returns the active vehicles mavType', () => {
      const id = registry.register(fakeTransport(), fakeParser(), fakeConfig);
      registry.recordHeartbeat(id, 1, 1, 13);
      registry.setActive(id, makeVehicleKey(id, 1, 1));
      expect(registry.getActiveVehicleType()).toBe(13);
    });
  });

  describe('stats', () => {
    it('recordPacketRx increments the rx counter and stamps lastPacketAt', () => {
      const id = registry.register(fakeTransport(), fakeParser(), fakeConfig);
      registry.recordPacketRx(id);
      registry.recordPacketRx(id);
      const stats = registry.getTransport(id)!.stats;
      expect(stats.packetsRx).toBe(2);
      expect(stats.lastPacketAt).not.toBeNull();
    });

    it('recordPacketTx increments the tx counter', () => {
      const id = registry.register(fakeTransport(), fakeParser(), fakeConfig);
      registry.recordPacketTx(id);
      expect(registry.getTransport(id)!.stats.packetsTx).toBe(1);
    });

    it('recordTransportError stores the error string', () => {
      const id = registry.register(fakeTransport(), fakeParser(), fakeConfig);
      registry.recordTransportError(id, 'EBADF');
      expect(registry.getTransport(id)!.stats.lastError).toBe('EBADF');
    });

    it('stats methods are silent no-ops on unknown transport', () => {
      expect(() => registry.recordPacketRx('nope')).not.toThrow();
      expect(() => registry.recordPacketTx('nope')).not.toThrow();
      expect(() => registry.recordTransportError('nope', 'x')).not.toThrow();
    });
  });
});
