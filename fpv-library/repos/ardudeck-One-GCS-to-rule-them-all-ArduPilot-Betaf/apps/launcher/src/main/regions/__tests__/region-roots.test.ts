import { describe, expect, it } from 'vitest';
import { join } from 'node:path';
import { buildRegionRoots, findGameRoots } from '../region-roots.js';

const APP_DIR = '/work/ardudeck/apps/launcher';

function existsIn(paths: string[]) {
  const set = new Set(paths);
  return (p: string) => set.has(p);
}

describe('findGameRoots', () => {
  it('finds the sibling checkout in dev', () => {
    const roots = findGameRoots({
      appDir: APP_DIR,
      isPackaged: false,
      exists: existsIn(['/work/ardudeck-game/godot']),
    });
    expect(roots).toEqual(['/work/ardudeck-game']);
  });

  it('puts the env override first', () => {
    const roots = findGameRoots({
      envGameRoot: '/elsewhere/game',
      appDir: APP_DIR,
      isPackaged: false,
      exists: existsIn(['/elsewhere/game/godot', '/work/ardudeck-game/godot']),
    });
    expect(roots[0]).toBe('/elsewhere/game');
    expect(roots).toContain('/work/ardudeck-game');
  });

  it('includes the packaged payload only when packaged', () => {
    const exists = existsIn(['/app/Resources/game/godot']);
    expect(
      findGameRoots({ appDir: APP_DIR, isPackaged: true, resourcesPath: '/app/Resources', exists }),
    ).toEqual([join('/app/Resources', 'game')]);
    expect(
      findGameRoots({ appDir: APP_DIR, isPackaged: false, resourcesPath: '/app/Resources', exists }),
    ).toEqual([]);
  });

  it('returns nothing when no candidate has a godot directory', () => {
    expect(findGameRoots({ appDir: APP_DIR, isPackaged: false, exists: () => false })).toEqual([]);
  });
});

describe('buildRegionRoots', () => {
  it('orders env override, then game terrain, then userData', () => {
    expect(
      buildRegionRoots({
        envRegionDir: '/custom/regions',
        gameRoots: ['/work/ardudeck-game'],
        userDataDir: '/userdata',
      }),
    ).toEqual([
      '/custom/regions',
      join('/work/ardudeck-game', 'godot', 'assets', 'terrain'),
      join('/userdata', 'regions'),
    ]);
  });

  it('deduplicates repeated roots', () => {
    const roots = buildRegionRoots({
      gameRoots: ['/g', '/g'],
      userDataDir: '/userdata',
    });
    expect(roots).toHaveLength(2);
  });
});
