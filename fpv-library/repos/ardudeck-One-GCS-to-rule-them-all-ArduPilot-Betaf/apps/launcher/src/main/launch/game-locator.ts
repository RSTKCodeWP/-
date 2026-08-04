import { dirname, join } from 'node:path';
import type { GameTarget } from '../../shared/ipc-channels.js';
import type { ExistsFn } from '../regions/region-roots.js';

export interface GameLocatorOptions {
  /** `ARDUDECK_GAME_BIN`, an exported game executable. Wins over everything. */
  envGameBin?: string | undefined;
  /** `ARDUDECK_GODOT_BIN`, for a Godot install in an unusual place. */
  envGodotBin?: string | undefined;
  gameRoots: string[];
  platform: NodeJS.Platform;
  exists: ExistsFn;
}

/** Where a Godot 4 binary usually is, per platform. */
function godotCandidates(platform: NodeJS.Platform): string[] {
  switch (platform) {
    case 'darwin':
      return [
        '/opt/homebrew/bin/godot',
        '/usr/local/bin/godot',
        '/Applications/Godot.app/Contents/MacOS/Godot',
      ];
    case 'win32':
      return ['C:\\Program Files\\Godot\\Godot.exe'];
    default:
      return ['/usr/bin/godot', '/usr/local/bin/godot'];
  }
}

/** Exported-game executable names to look for inside a game root. */
function exportedCandidates(root: string, platform: NodeJS.Platform): string[] {
  const dir = join(root, 'build');
  switch (platform) {
    case 'darwin':
      return [join(dir, 'ArduDeck Trainer.app', 'Contents', 'MacOS', 'ArduDeck Trainer')];
    case 'win32':
      return [join(dir, 'ArduDeckTrainer.exe')];
    default:
      return [join(dir, 'ArduDeckTrainer.x86_64'), join(dir, 'ArduDeckTrainer')];
  }
}

export interface GameLocateResult {
  target: GameTarget | null;
  error: string | null;
}

/**
 * Decide how to start the game. An exported build is preferred when one exists; otherwise
 * the launcher drives a Godot binary against the project source, which is the only shape
 * that exists today. Both are the same contract downstream: a command, some fixed args,
 * and the config appended by the caller.
 */
export function findGameTarget(opts: GameLocatorOptions): GameLocateResult {
  if (opts.envGameBin) {
    if (!opts.exists(opts.envGameBin)) {
      return { target: null, error: `ARDUDECK_GAME_BIN points at ${opts.envGameBin}, which does not exist` };
    }
    return {
      target: {
        command: opts.envGameBin,
        args: [],
        cwd: dirname(opts.envGameBin),
        label: 'Exported build (ARDUDECK_GAME_BIN)',
        dev: false,
      },
      error: null,
    };
  }

  for (const root of opts.gameRoots) {
    for (const bin of exportedCandidates(root, opts.platform)) {
      if (opts.exists(bin)) {
        return {
          target: { command: bin, args: [], cwd: dirname(bin), label: 'Exported build', dev: false },
          error: null,
        };
      }
    }
  }

  const projectRoot = opts.gameRoots.find((root) => opts.exists(join(root, 'godot', 'project.godot')));
  if (!projectRoot) {
    return {
      target: null,
      error:
        'No game found. Set ARDUDECK_GAME_BIN to an exported build, or ARDUDECK_GAME_ROOT to a game checkout containing godot/project.godot.',
    };
  }

  const godot = [opts.envGodotBin, ...godotCandidates(opts.platform)]
    .filter((c): c is string => Boolean(c))
    .find((c) => opts.exists(c));
  if (!godot) {
    return {
      target: null,
      error: `Found the game project at ${projectRoot} but no Godot binary to run it. Set ARDUDECK_GODOT_BIN.`,
    };
  }

  return {
    target: {
      command: godot,
      args: ['--path', join(projectRoot, 'godot')],
      cwd: projectRoot,
      label: 'Godot (project source)',
      dev: true,
    },
    error: null,
  };
}

/**
 * Godot only exposes arguments after a bare `--` through `get_cmdline_user_args`, so the
 * separator is not optional. The game also reads ARDUDECK_CONFIG from the environment, which
 * is what actually survives a Steam launch wrapper, so the two are set together on purpose.
 */
export function gameArgsForConfig(target: GameTarget, configPath: string): string[] {
  return [...target.args, '--', `--ardudeck-config=${configPath}`];
}
