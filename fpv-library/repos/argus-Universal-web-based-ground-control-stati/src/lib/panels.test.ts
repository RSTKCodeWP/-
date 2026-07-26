import { describe, it, expect } from 'vitest';
import { panels, PANEL_LOADERS, type PanelId } from './panels.svelte';

describe('PanelRegistry', () => {
  it('starts with no panels open', () => {
    expect(panels.isOpen('logPanel')).toBe(false);
    expect(panels.isOpen('video')).toBe(false);
  });

  it('open adds panel to open set', () => {
    panels.open('logPanel');
    expect(panels.isOpen('logPanel')).toBe(true);
    panels.close('logPanel');
  });

  it('close removes panel from open set', () => {
    panels.open('video');
    panels.close('video');
    expect(panels.isOpen('video')).toBe(false);
  });

  it('toggle opens closed panel', () => {
    panels.close('inspector');
    panels.toggle('inspector');
    expect(panels.isOpen('inspector')).toBe(true);
    panels.close('inspector');
  });

  it('toggle closes open panel', () => {
    panels.open('console');
    panels.toggle('console');
    expect(panels.isOpen('console')).toBe(false);
  });

  it('multiple panels can be open simultaneously', () => {
    panels.open('logPanel');
    panels.open('video');
    panels.open('calibration');
    expect(panels.isOpen('logPanel')).toBe(true);
    expect(panels.isOpen('video')).toBe(true);
    expect(panels.isOpen('calibration')).toBe(true);
    panels.close('logPanel');
    panels.close('video');
    panels.close('calibration');
  });

  it('closing already closed panel is no-op', () => {
    panels.close('fft');
    panels.close('fft');
    expect(panels.isOpen('fft')).toBe(false);
  });

  it('opening already open panel is no-op', () => {
    panels.open('pid');
    panels.open('pid');
    expect(panels.isOpen('pid')).toBe(true);
    panels.close('pid');
  });
});

describe('PANEL_LOADERS', () => {
  it('has a loader for every panel ID', () => {
    const ids: PanelId[] = [
      'logPanel',
      'video',
      'calibration',
      'shortcuts',
      'inspector',
      'console',
      'motorTest',
      'rcCal',
      'failsafe',
      'powerCal',
      'escCal',
      'frameSelect',
      'pid',
      'autoTune',
      'flightModes',
      'setupWizard',
      'paramDiff',
      'flightReport',
      'logViewer',
      'fft',
      'compass3d',
      'advCmd',
      'overlapCalc',
      'corridor',
      'poi',
      'annotation',
      'remote',
      'role',
      'airspace',
      'offlineMap',
      'mission3d',
      'gimbal',
      'dashboard',
      'aiPlanner',
      'script',
      'ortho',
      'aiAnnotation',
      'scheduler',
      'posSource',
      'ntrip',
      'fleet',
      'terrainProfile',
    ];
    for (const id of ids) {
      expect(PANEL_LOADERS[id]).toBeDefined();
      expect(typeof PANEL_LOADERS[id]).toBe('function');
    }
  });

  it('loaders return promises', async () => {
    const result = PANEL_LOADERS['shortcuts']();
    expect(result).toBeInstanceOf(Promise);
    await result.catch(() => {});
  });

  it('has exactly 42 panel loaders', () => {
    // MultiVehiclePanel removed 2026-07 (placeholder switch — FleetDashboard
    // is the real multi-vehicle UI).
    expect(Object.keys(PANEL_LOADERS).length).toBe(42);
  });

  it('shortcuts loader resolves immediately', async () => {
    const mod = await PANEL_LOADERS.shortcuts();
    expect(mod).toHaveProperty('default');
  });

  it('all loaders return thenables', () => {
    for (const [id, loader] of Object.entries(PANEL_LOADERS)) {
      const result = loader();
      expect(typeof result.then, `${id} loader did not return a thenable`).toBe('function');
      result.catch(() => {});
    }
  });
});
