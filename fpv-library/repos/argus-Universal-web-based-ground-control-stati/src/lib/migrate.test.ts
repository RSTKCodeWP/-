import { describe, it, expect, beforeEach, vi } from 'vitest';
import { migrateLocalStorage } from './migrate';

function makeStorage(): Storage {
  const store = new Map<string, string>();
  return {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => {
      store.set(k, v);
    },
    removeItem: (k: string) => {
      store.delete(k);
    },
    clear: () => store.clear(),
    get length() {
      return store.size;
    },
    key: (i: number) => [...store.keys()][i] ?? null,
  };
}

let storage: Storage;

beforeEach(() => {
  storage = makeStorage();
  vi.stubGlobal('localStorage', storage);
});

describe('migrateLocalStorage', () => {
  it('migrates a known fixed key', () => {
    storage.setItem('pllink_v3_settings', '{"dark":true}');
    migrateLocalStorage();
    expect(storage.getItem('argus_settings')).toBe('{"dark":true}');
    expect(storage.getItem('pllink_v3_settings')).toBeNull();
  });

  it('does not overwrite existing new key', () => {
    storage.setItem('pllink_v3_settings', '{"old":1}');
    storage.setItem('argus_settings', '{"new":2}');
    migrateLocalStorage();
    expect(storage.getItem('argus_settings')).toBe('{"new":2}');
  });

  it('is idempotent', () => {
    storage.setItem('pllink_locale', 'en');
    migrateLocalStorage();
    migrateLocalStorage();
    expect(storage.getItem('argus_locale')).toBe('en');
    expect(storage.getItem('pllink_locale')).toBeNull();
  });

  it('migrates dynamic prefix keys', () => {
    storage.setItem('pllink_ai_annotations_photo1.jpg', '[{"x":1}]');
    storage.setItem('pllink_mission_test_route', '{"wps":[]}');
    migrateLocalStorage();
    expect(storage.getItem('argus_ai_annotations_photo1.jpg')).toBe('[{"x":1}]');
    expect(storage.getItem('argus_mission_test_route')).toBe('{"wps":[]}');
    expect(storage.getItem('pllink_ai_annotations_photo1.jpg')).toBeNull();
    expect(storage.getItem('pllink_mission_test_route')).toBeNull();
  });

  it('handles empty localStorage gracefully', () => {
    migrateLocalStorage();
    expect(storage.length).toBe(0);
  });

  it('migrates multiple keys at once', () => {
    storage.setItem('pllink_locale', 'ja');
    storage.setItem('pllink_units', 'imperial');
    storage.setItem('pllink_flights', '[]');
    migrateLocalStorage();
    expect(storage.getItem('argus_locale')).toBe('ja');
    expect(storage.getItem('argus_units')).toBe('imperial');
    expect(storage.getItem('argus_flights')).toBe('[]');
  });
});
