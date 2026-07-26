/**
 * wfb-ng receiver manager - the "plug the dongle into this computer" path.
 *
 * Owns everything around the (bundled) `ardudeck-wfb-rx` receiver sidecar:
 * dongle detection per OS, gs.key storage, spawn/stop lifecycle and a status
 * snapshot the UI renders as plain-language chips. When the sidecar binary is
 * absent the status says so clearly - every other piece works regardless, so
 * shipping the binary is the only remaining step to full plug-and-play.
 */

import { spawn, spawnSync, execFile, type ChildProcess } from 'node:child_process';
import { join } from 'node:path';
import { existsSync, mkdirSync, copyFileSync } from 'node:fs';
import { app } from 'electron';
import { mediaBinariesDownloader } from './media-binaries-downloader.js';
import {
  findDongleMac,
  findDongleLinux,
  findDongleWindows,
  buildReceiverArgs,
  WFB_DEFAULT_CHANNEL,
  type DetectedDongle,
} from './wfbng-dongle.js';
import type { WfbngStatus } from '../../shared/camera-types.js';

export const WFB_RX_BINARY = 'ardudeck-wfb-rx';


class WfbngReceiver {
  private proc: ChildProcess | null = null;
  private channel = WFB_DEFAULT_CHANNEL;
  private bandwidth: 20 | 40 = 20;
  /** Latest counters parsed from the receiver's "stats wifi=.. wfb=.. rtp=.." lines. */
  private lastStats: { wifi: number; wfb: number; rtp: number } | null = null;
  private logSink: ((level: 'info' | 'warn' | 'error', line: string) => void) | null = null;
  /** In-flight start, shared by concurrent ensureRunning callers. */
  private starting: Promise<{ ok: true } | { ok: false; error: string }> | null = null;

  /** Route receiver output into the app log (wired once from ipc-handlers). */
  setLogSink(sink: (level: 'info' | 'warn' | 'error', line: string) => void): void {
    this.logSink = sink;
  }

  private dir(): string {
    const d = join(app.getPath('userData'), 'wfbng');
    mkdirSync(d, { recursive: true });
    return d;
  }

  gsKeyPath(): string {
    return join(this.dir(), 'gs.key');
  }

  importGsKey(sourcePath: string): void {
    copyFileSync(sourcePath, this.gsKeyPath());
  }

  setOptions(opts: { channel?: number; bandwidth?: 20 | 40 }): void {
    if (opts.channel) this.channel = opts.channel;
    if (opts.bandwidth) this.bandwidth = opts.bandwidth;
  }

  binaryPath(): string | null {
    const ext = process.platform === 'win32' ? '.exe' : '';
    const appPath = app.getAppPath();
    const base = app.isPackaged ? appPath.replace('app.asar', 'app.asar.unpacked') : appPath;
    const bundled = join(base, 'resources', 'bin', process.platform, WFB_RX_BINARY + ext);
    if (existsSync(bundled)) return bundled;
    const downloaded = mediaBinariesDownloader.binaryPath('ardudeck-wfb-rx');
    if (existsSync(downloaded)) return downloaded;
    const probe = spawnSync(WFB_RX_BINARY, ['--version'], { stdio: 'ignore' });
    if (!probe.error) return WFB_RX_BINARY;
    return null;
  }

  /** Fetch the receiver from ArduDeck's release assets when not bundled. */
  async download(onLog?: (line: string) => void): Promise<{ ok: boolean; error?: string }> {
    if (this.binaryPath()) return { ok: true };
    return mediaBinariesDownloader.ensureWfbRx(onLog);
  }

  async detectDongle(): Promise<DetectedDongle | null> {
    const run = (cmd: string, args: string[]): Promise<string> =>
      new Promise((resolve) => {
        execFile(cmd, args, { timeout: 8000, maxBuffer: 4 * 1024 * 1024 }, (_err, stdout) => resolve(stdout ?? ''));
      });
    try {
      if (process.platform === 'darwin') {
        return findDongleMac(await run('system_profiler', ['-json', 'SPUSBDataType']));
      }
      if (process.platform === 'linux') {
        return findDongleLinux(await run('lsusb', []));
      }
      if (process.platform === 'win32') {
        const out = await run('powershell', [
          '-NoProfile', '-Command',
          "Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match 'VID_0BDA' } | Select-Object -ExpandProperty InstanceId",
        ]);
        return findDongleWindows(out);
      }
    } catch {
      /* detection is best-effort */
    }
    return null;
  }

  async getStatus(): Promise<WfbngStatus> {
    const dongle = await this.detectDongle();
    return {
      dongleName: dongle ? dongle.name : null,
      receiverInstalled: this.binaryPath() !== null,
      gsKeyImported: existsSync(this.gsKeyPath()),
      running: this.proc !== null && this.proc.exitCode === null,
      channel: this.channel,
      bandwidth: this.bandwidth,
      stats: this.lastStats,
    };
  }

  /**
   * Make sure the receiver is running for dongle-mode video. Returns a
   * plain-language error naming exactly what is missing when it cannot.
   *
   * Concurrency-safe: several render surfaces (Vision panel, OSD backdrop,
   * grid tiles) start the same feed near-simultaneously. Without coalescing,
   * each call passes the "is it running?" check before any has spawned, and
   * they all spawn - a claim-storm where every receiver but one dies with
   * "adapter in use by another program". A single in-flight promise collapses
   * them into one spawn attempt.
   */
  async ensureRunning(outputPort: number): Promise<{ ok: true } | { ok: false; error: string }> {
    if (this.proc && this.proc.exitCode === null) return { ok: true };
    if (this.starting) return this.starting;
    this.starting = this.doStart(outputPort).finally(() => { this.starting = null; });
    return this.starting;
  }

  private async doStart(outputPort: number): Promise<{ ok: true } | { ok: false; error: string }> {
    if (this.proc && this.proc.exitCode === null) return { ok: true };

    const binary = this.binaryPath();
    if (!binary) {
      return {
        ok: false,
        error:
          'The wfb-ng receiver component is not available for this platform yet. Until it ships, use a ground station (Android PixelPilot or a Linux box) that forwards video to this computer - switch the feed to Network mode.',
      };
    }
    const dongle = await this.detectDongle();
    if (!dongle) {
      return { ok: false, error: 'No WiFi receiver dongle found. Plug the RTL8812AU dongle from the camera kit into this computer.' };
    }
    if (!existsSync(this.gsKeyPath())) {
      return {
        ok: false,
        error: 'The pairing key (gs.key) has not been imported. Get it from the camera (it creates gs.key on first boot) and import it in the feed setup.',
      };
    }

    this.lastStats = null;
    this.proc = spawn(binary, buildReceiverArgs({
      gsKeyPath: this.gsKeyPath(),
      channel: this.channel,
      bandwidth: this.bandwidth,
      outputPort,
    }), { stdio: ['ignore', 'pipe', 'pipe'] });

    // stdout: periodic "stats wifi=N wfb=N rtp=N" keepalives -> status.
    this.proc.stdout?.on('data', (buf: Buffer) => {
      for (const line of buf.toString().split('\n')) {
        const m = line.match(/^stats wifi=(\d+) wfb=(\d+) rtp=(\d+)/);
        if (m) this.lastStats = { wifi: Number(m[1]), wfb: Number(m[2]), rtp: Number(m[3]) };
      }
    });
    // stderr: human-readable receiver log -> app console.
    this.proc.stderr?.on('data', (buf: Buffer) => {
      for (const raw of buf.toString().split('\n')) {
        const line = raw.trim();
        if (!line) continue;
        const level = line.startsWith('[error]') ? 'error' : line.startsWith('[warn]') ? 'warn' : 'info';
        this.logSink?.(level, `wfb-rx: ${line.replace(/^\[\w+\]\s*/, '')}`);
      }
    });
    this.proc.on('exit', (code) => {
      this.logSink?.(code === 0 ? 'info' : 'warn', `wfb-rx exited (code ${code ?? 'signal'})`);
      this.proc = null;
    });
    return { ok: true };
  }

  getLastStats(): { wifi: number; wfb: number; rtp: number } | null {
    return this.lastStats;
  }

  stop(): void {
    if (this.proc && this.proc.exitCode === null) {
      this.proc.kill('SIGTERM');
    }
    this.proc = null;
  }
}

export const wfbngReceiver = new WfbngReceiver();
