// sitl.ts — ArduPilot SITL process launcher and lifecycle manager
// SPDX-License-Identifier: GPL-3.0-only

import { spawn, type ChildProcess } from 'node:child_process';
import { access, constants } from 'node:fs/promises';
import { createConnection } from 'node:net';
import { createInterface } from 'node:readline';
import { EventEmitter } from 'node:events';
import { join } from 'node:path';
import { homedir } from 'node:os';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SitlConfig {
  ardupilotHome: string;    // Path to ArduPilot source (default ~/.ardupilot)
  vehicle: string;          // ArduCopter, ArduPlane, ArduRover
  drones: number;           // Number of instances
  lat: number;              // Home latitude
  lon: number;              // Home longitude
  alt: number;              // Home altitude (default 0)
  heading: number;          // Home heading (default 0)
  speedup: number;          // Simulation speed (default 1)
  wind?: { speed: number; direction: number };
  baseTcpPort: number;      // Base TCP port (default 5760, each instance +10)
  extraArgs?: string[];     // Additional args to pass to sim_vehicle.py (e.g. from preset)
}

export interface SitlInstance {
  sysId: number;
  tcpPort: number;
  pid: number;
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

const DEFAULTS: SitlConfig = {
  ardupilotHome: join(homedir(), '.ardupilot'),
  vehicle: 'ArduCopter',
  drones: 1,
  lat: 12.9716,
  lon: 77.5946,
  alt: 0,
  heading: 0,
  speedup: 1,
  baseTcpPort: 5760,
};

const TCP_POLL_MS = 500;
const TCP_TIMEOUT_MS = 60_000;
const SIGKILL_TIMEOUT_MS = 5_000;

// ---------------------------------------------------------------------------
// SitlLauncher
// ---------------------------------------------------------------------------

export class SitlLauncher extends EventEmitter {
  private readonly config: SitlConfig;
  private readonly children: ChildProcess[] = [];
  private instances: SitlInstance[] = [];

  constructor(config: Partial<SitlConfig> & Pick<SitlConfig, 'lat' | 'lon'>) {
    super();
    this.config = { ...DEFAULTS, ...config };
  }

  /** Validate environment, spawn SITL processes, wait for TCP readiness. */
  async launch(): Promise<SitlInstance[]> {
    const scriptPath = join(
      this.config.ardupilotHome,
      'Tools',
      'autotest',
      'sim_vehicle.py',
    );

    await access(scriptPath, constants.F_OK).catch(() => {
      throw new Error(
        `sim_vehicle.py not found at ${scriptPath}. ` +
          `Set ardupilotHome to the ArduPilot source root.`,
      );
    });

    const { vehicle, drones, lat, lon, alt, heading, speedup, baseTcpPort } =
      this.config;

    const homeStr = `${lat},${lon},${alt},${heading}`;

    // Build arguments common to every invocation
    const args: string[] = [
      scriptPath,
      '-v', vehicle,
      '--no-mavproxy',
      '-l', homeStr,
      '--speedup', String(speedup),
    ];

    // TCP output ports
    const ports: number[] = [];
    for (let i = 0; i < drones; i++) {
      const port = baseTcpPort + i * 10;
      ports.push(port);
      args.push(`--out=tcpin:0.0.0.0:${port}`);
    }

    // Multi-drone flags
    if (drones > 1) {
      args.push('--count', String(drones), '--auto-sysid');
    }

    // Wind parameters (passed as SITL model params)
    if (this.config.wind) {
      const { speed, direction } = this.config.wind;
      args.push(
        '--sitl-wind', `${speed},${direction},0,0`,
      );
    }

    // Extra args from preset or CLI
    if (this.config.extraArgs?.length) {
      args.push(...this.config.extraArgs);
    }

    // Spawn the process
    const proc = spawn('python3', args, {
      cwd: this.config.ardupilotHome,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    this.children.push(proc);

    // Stream stdout / stderr line-by-line
    if (proc.stdout) {
      const rl = createInterface({ input: proc.stdout });
      rl.on('line', (line: string) => this.emit('stdout', line));
    }
    if (proc.stderr) {
      const rl = createInterface({ input: proc.stderr });
      rl.on('line', (line: string) => this.emit('stderr', line));
    }

    proc.on('exit', (code) => this.emit('exit', code ?? 1));

    // Wait for every TCP port to become connectable
    await Promise.all(ports.map((p) => waitForTcpReady(p)));

    // Build instance metadata
    this.instances = ports.map((port, i) => ({
      sysId: i + 1,
      tcpPort: port,
      pid: proc.pid ?? -1,
    }));

    this.emit('ready', { instances: this.instances });
    return this.instances;
  }

  /** Gracefully terminate all SITL child processes. */
  async shutdown(): Promise<void> {
    const killPromises = this.children.map(
      (child) =>
        new Promise<void>((resolve) => {
          if (!child.pid || child.killed) {
            resolve();
            return;
          }

          const forceKill = setTimeout(() => {
            try { child.kill('SIGKILL'); } catch { /* already dead */ }
          }, SIGKILL_TIMEOUT_MS);

          child.once('exit', () => {
            clearTimeout(forceKill);
            resolve();
          });

          child.kill('SIGTERM');
        }),
    );

    await Promise.all(killPromises);
    this.children.length = 0;
    this.instances = [];
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Poll a TCP port until a connection succeeds or the timeout expires.
 * Resolves when the port accepts a connection; rejects on timeout.
 */
function waitForTcpReady(port: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + TCP_TIMEOUT_MS;

    const attempt = () => {
      if (Date.now() > deadline) {
        reject(new Error(`TCP port ${port} not ready after ${TCP_TIMEOUT_MS}ms`));
        return;
      }

      const sock = createConnection({ port, host: '127.0.0.1' }, () => {
        sock.destroy();
        resolve();
      });

      sock.on('error', () => {
        sock.destroy();
        setTimeout(attempt, TCP_POLL_MS);
      });
    };

    attempt();
  });
}
