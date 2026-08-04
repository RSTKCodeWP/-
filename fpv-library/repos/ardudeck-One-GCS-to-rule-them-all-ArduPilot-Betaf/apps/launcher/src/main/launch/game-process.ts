import { spawn, type ChildProcess } from 'node:child_process';
import type { GameLogLine, GameStatus, GameTarget } from '../../shared/ipc-channels.js';
import { gameArgsForConfig } from './game-locator.js';

export interface StartGameOptions {
  target: GameTarget;
  configPath: string;
  regionName: string;
}

/**
 * Owns the single game child process.
 *
 * The launcher deliberately stays alive as the game's PARENT for the whole session: Steam
 * attributes playtime and attaches its overlay to the launched process tree, so `detached`
 * must stay false and the child must never be `unref`'d. That is the one hard requirement
 * on this class; everything else here is reporting.
 */
export class GameProcess {
  private child: ChildProcess | null = null;
  private status: GameStatus = {
    state: 'idle',
    pid: null,
    exitCode: null,
    signal: null,
    error: null,
    configPath: null,
    regionName: null,
    startedAt: null,
  };

  constructor(
    private readonly onStatus: (status: GameStatus) => void,
    private readonly onLog: (line: GameLogLine) => void,
  ) {}

  getStatus(): GameStatus {
    return this.status;
  }

  isRunning(): boolean {
    return this.child !== null && this.child.exitCode === null && !this.child.killed;
  }

  private setStatus(patch: Partial<GameStatus>): void {
    this.status = { ...this.status, ...patch };
    this.onStatus(this.status);
  }

  private emitLines(stream: 'stdout' | 'stderr', chunk: Buffer): void {
    for (const line of chunk.toString('utf8').split(/\r?\n/)) {
      if (line.trim().length > 0) this.onLog({ stream, line });
    }
  }

  start(opts: StartGameOptions): number {
    if (this.isRunning()) {
      throw new Error('The game is already running');
    }

    this.setStatus({
      state: 'starting',
      pid: null,
      exitCode: null,
      signal: null,
      error: null,
      configPath: opts.configPath,
      regionName: opts.regionName,
      startedAt: Date.now(),
    });

    const args = gameArgsForConfig(opts.target, opts.configPath);
    const child = spawn(opts.target.command, args, {
      // Stay the parent. See the class comment: this is the Steam attribution requirement.
      detached: false,
      stdio: ['ignore', 'pipe', 'pipe'],
      cwd: opts.target.cwd,
      env: {
        ...process.env,
        // Second channel to the same value. The `--ardudeck-config` argument is the primary
        // one; this survives launch wrappers that rewrite argv.
        ARDUDECK_CONFIG: opts.configPath,
      },
    });
    this.child = child;

    child.stdout?.on('data', (c: Buffer) => this.emitLines('stdout', c));
    child.stderr?.on('data', (c: Buffer) => this.emitLines('stderr', c));

    child.on('spawn', () => {
      this.setStatus({ state: 'running', pid: child.pid ?? null });
    });
    child.on('error', (err) => {
      this.child = null;
      this.setStatus({ state: 'failed', error: err.message, pid: null });
    });
    child.on('exit', (code, signal) => {
      this.child = null;
      // A non-zero exit is worth surfacing, but the launcher must survive it either way:
      // the player's next action is to change something and press Start again.
      this.setStatus({
        state: code === 0 || code === null ? 'exited' : 'failed',
        exitCode: code,
        signal: signal ?? null,
        pid: null,
        error: code !== null && code !== 0 ? `The game exited with code ${code}` : null,
      });
    });

    return child.pid ?? -1;
  }

  stop(): void {
    if (!this.child) return;
    this.child.kill('SIGTERM');
  }

  /** Called on launcher shutdown so the game never outlives its parent. */
  dispose(): void {
    if (!this.child) return;
    this.child.kill('SIGKILL');
    this.child = null;
  }
}
