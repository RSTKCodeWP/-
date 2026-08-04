import { describe, expect, it } from 'vitest';
import { findGameTarget, gameArgsForConfig } from '../game-locator.js';

function existsIn(paths: string[]) {
  const set = new Set(paths);
  return (p: string) => set.has(p);
}

describe('findGameTarget', () => {
  it('drives Godot against the project source when there is no exported build', () => {
    const { target, error } = findGameTarget({
      gameRoots: ['/game'],
      platform: 'darwin',
      exists: existsIn(['/game/godot/project.godot', '/opt/homebrew/bin/godot']),
    });
    expect(error).toBeNull();
    expect(target).toEqual({
      command: '/opt/homebrew/bin/godot',
      args: ['--path', '/game/godot'],
      cwd: '/game',
      label: 'Godot (project source)',
      dev: true,
    });
  });

  it('prefers an exported build over the project source', () => {
    const { target } = findGameTarget({
      gameRoots: ['/game'],
      platform: 'linux',
      exists: existsIn([
        '/game/build/ArduDeckTrainer.x86_64',
        '/game/godot/project.godot',
        '/usr/bin/godot',
      ]),
    });
    expect(target?.command).toBe('/game/build/ArduDeckTrainer.x86_64');
    expect(target?.cwd).toBe('/game/build');
    expect(target?.dev).toBe(false);
  });

  it('honours ARDUDECK_GAME_BIN above everything', () => {
    const { target } = findGameTarget({
      envGameBin: '/opt/trainer',
      gameRoots: ['/game'],
      platform: 'linux',
      exists: existsIn(['/opt/trainer', '/game/godot/project.godot', '/usr/bin/godot']),
    });
    expect(target?.command).toBe('/opt/trainer');
  });

  it('reports a bad ARDUDECK_GAME_BIN instead of silently falling through', () => {
    const { target, error } = findGameTarget({
      envGameBin: '/opt/missing',
      gameRoots: ['/game'],
      platform: 'linux',
      exists: existsIn(['/game/godot/project.godot', '/usr/bin/godot']),
    });
    expect(target).toBeNull();
    expect(error).toContain('/opt/missing');
  });

  it('distinguishes no project from no Godot', () => {
    expect(findGameTarget({ gameRoots: [], platform: 'linux', exists: () => false }).error).toContain(
      'No game found',
    );
    const noGodot = findGameTarget({
      gameRoots: ['/game'],
      platform: 'linux',
      exists: existsIn(['/game/godot/project.godot']),
    });
    expect(noGodot.error).toContain('no Godot binary');
  });
});

describe('gameArgsForConfig', () => {
  it('separates user args with a bare -- so Godot forwards them', () => {
    const target = { command: 'godot', args: ['--path', '/game/godot'], cwd: '/game', label: '', dev: true };
    expect(gameArgsForConfig(target, '/cfg/launch-config.json')).toEqual([
      '--path',
      '/game/godot',
      '--',
      '--ardudeck-config=/cfg/launch-config.json',
    ]);
  });
});
