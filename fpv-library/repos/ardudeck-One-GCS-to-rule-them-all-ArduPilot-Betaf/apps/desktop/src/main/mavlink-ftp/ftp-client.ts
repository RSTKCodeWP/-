/**
 * MAVLink FTP Client
 *
 * Implements the MAVLink FILE_TRANSFER_PROTOCOL for downloading files
 * from a flight controller's virtual filesystem.
 *
 * Uses sequential ReadFile (request/response per chunk) which is simple,
 * reliable, and fast on USB serial where round-trip latency is <1ms.
 *
 * Reference: MissionPlanner MAVFtp.cs, mavlink.io/en/services/ftp.html
 */

import {
  FtpOpcode,
  FtpError,
  FTP_ERROR_NAMES,
  FTP_READ_SIZE,
  FTP_WRITE_SIZE,
  FTP_TIMEOUT_MS,
  FTP_MAX_RETRIES,
  type FtpPayload,
  serializeFtpPayload,
  parseFtpPayload,
} from './ftp-types.js';

// ─── Types ───────────────────────────────────────────────────────────────────

/** Callback to send a raw FTP payload over MAVLink */
export type SendFtpPacket = (ftpPayload: Uint8Array) => Promise<void>;

/** Progress callback */
export type FtpProgressCallback = (received: number, total: number) => void;

/** Log callback */
export type FtpLogCallback = (level: 'info' | 'warn' | 'error' | 'debug', message: string) => void;

export interface FtpClientOptions {
  /** Function to send a serialized FTP payload via FILE_TRANSFER_PROTOCOL */
  sendPacket: SendFtpPacket;
  /** Log callback */
  log?: FtpLogCallback;
  /** Read chunk size (default: 110, matching Mission Planner) */
  readSize?: number;
}

/** One entry returned by ListDirectory. */
export type DirectoryEntry =
  | { kind: 'dir'; name: string }
  | { kind: 'file'; name: string; size: number };

// ─── FTP Client ──────────────────────────────────────────────────────────────

export class MavlinkFtpClient {
  private sendPacket: SendFtpPacket;
  private log: FtpLogCallback;
  private readSize: number;
  private seqNumber = 0;
  private sessionId = 0;

  /** Pending response resolver - set by sendRequest(), resolved by handleResponse() */
  private pendingResolve: ((payload: FtpPayload | null) => void) | null = null;
  private pendingTimer: NodeJS.Timeout | null = null;

  constructor(options: FtpClientOptions) {
    this.sendPacket = options.sendPacket;
    this.log = options.log ?? (() => {});
    this.readSize = options.readSize ?? FTP_READ_SIZE;
  }

  /**
   * Handle an incoming FTP response from the flight controller.
   * Called by the MAVLink message router when FILE_TRANSFER_PROTOCOL (110) is received.
   */
  handleResponse(rawPayload: Uint8Array): void {
    const payload = parseFtpPayload(rawPayload);

    if (this.pendingResolve) {
      if (this.pendingTimer) {
        clearTimeout(this.pendingTimer);
        this.pendingTimer = null;
      }
      const resolve = this.pendingResolve;
      this.pendingResolve = null;
      resolve(payload);
    }
  }

  // ─── High-level API ──────────────────────────────────────────────────────

  /**
   * Download a file from the FC's virtual filesystem.
   * Uses sequential ReadFile (one request per chunk, waits for response).
   * Returns the file contents as a Uint8Array, or null on failure.
   */
  async downloadFile(
    path: string,
    progress?: FtpProgressCallback,
  ): Promise<Uint8Array | null> {
    try {
      // Reset sessions to clean any stale state
      await this.resetSessions();

      // Open file and get size
      const fileSize = await this.openFileRO(path);
      if (fileSize === null) {
        this.log('warn', `FTP: file not found or open failed: ${path}`);
        return null;
      }

      this.log('info', `FTP: opened ${path} (${fileSize} bytes)`);

      if (fileSize === 0) {
        await this.terminateSession();
        return new Uint8Array(0);
      }

      // Download using sequential reads
      const data = await this.sequentialDownload(fileSize, progress);

      // Cleanup session
      await this.terminateSession();

      if (!data) {
        this.log('warn', 'FTP: download failed');
        return null;
      }

      return data;
    } catch (err) {
      this.log('error', `FTP error: ${err instanceof Error ? err.message : String(err)}`);
      try { await this.terminateSession(); } catch { /* ignore */ }
      return null;
    }
  }

  /** Cleanup: reset all sessions on the FC */
  async cleanup(): Promise<void> {
    try {
      await this.resetSessions();
    } catch { /* ignore */ }
    this.clearPending();
  }

  /**
   * List the contents of a directory on the FC's filesystem.
   *
   * MAVLink-FTP packs multiple entries into one Ack response (max ~239 bytes
   * payload) so for big directories we must re-request with a higher offset
   * (where offset = "skip first N entries already received") until we get a
   * NAK with EOF. Each entry in the Ack payload is null-terminated and tagged
   * by its first character:
   *   'F' file       - "F<name>\t<size>\0"
   *   'D' directory  - "D<name>\0"
   *   'S' skip       - "S\0" (entry that the FC chose not to surface)
   *
   * Reference: https://mavlink.io/en/services/ftp.html#listdirectory
   *
   * Returns null on transport failure / NAK other than EOF; returns [] for an
   * empty (but reachable) directory.
   */
  async listDirectory(path: string): Promise<{ entries: DirectoryEntry[] } | { error: string }> {
    // Fast path: try without a session reset. LIST is stateless on the FC
    // side per ArduPilot's GCS_FTP::list_dir, so most calls don't need it.
    // If anything fails - even FileNotFound - we reset and retry once.
    // The retry isn't really for "find the missing dir on second attempt",
    // it's because ArduPilot's FTP server leaves residual state after a
    // NAK that wedges the *next* unrelated call too. Resetting now means
    // the user's next navigation gets a clean server. Cost on a genuine
    // miss is ~1 extra round-trip (negligible on localhost/USB serial).
    const first = await this.listDirectoryOnce(path);
    if ('entries' in first) return first;

    this.log('debug', `FTP: listDirectory ${path} first attempt failed (${first.error}); resetting sessions and retrying`);
    await this.resetSessions();
    return this.listDirectoryOnce(path);
  }

  private async listDirectoryOnce(path: string): Promise<{ entries: DirectoryEntry[] } | { error: string }> {
    const pathBytes = new TextEncoder().encode(path);
    const data = new Uint8Array(pathBytes.length + 1); // null-terminated
    data.set(pathBytes);

    const entries: DirectoryEntry[] = [];
    // Names we've already added, used to dedupe across pages. ArduPilot's
    // iterator can re-emit the same entry on consecutive batches when its
    // internal cursor and our requested offset drift (different batch sizes
    // per call, virtual mount injection, etc.) - especially on SITL POSIX.
    // A real directory can't legitimately contain two entries with the same
    // name, so any duplicate is glitch noise we drop.
    const seenNames = new Set<string>();
    // Tracks the total entry index ArduPilot has returned to us across pages,
    // including ones we filtered (".", "..") or that came back as 'S' (skip)
    // tags. This is what 'offset' on the next request must match - using
    // entries.length here would re-request entries we already filtered,
    // producing duplicates. ArduPilot's view of "where we are" is parsed-count,
    // not visible-count.
    let totalParsed = 0;
    const MAX_ENTRIES = 1000; // safety cap so a misbehaving FC can't loop us forever

    while (entries.length < MAX_ENTRIES) {
      let resp: FtpPayload | null = null;
      for (let retry = 0; retry < FTP_MAX_RETRIES; retry++) {
        resp = await this.sendRequest({
          opcode: FtpOpcode.ListDirectory,
          session: 0,
          // 'offset' here is "first entry index to return", not byte offset.
          offset: totalParsed,
          // Per the MAVLink-FTP spec, `size` is the count of valid bytes in
          // the data field. ArduPilot's server writes `payload[12 + size] = 0`
          // to null-terminate before reading the path, so `size: 0` corrupts
          // the path to an empty string. Mission Planner sets size = path
          // byte count - we match that.
          size: pathBytes.length,
          data,
        });
        if (resp) break;
      }
      if (!resp) {
        this.log('warn', `FTP: ListDirectory ${path} timed out`);
        return { error: 'no response from FC (timed out)' };
      }

      if (resp.opcode === FtpOpcode.Nak) {
        const errCode = resp.data[0] ?? 0;
        if (errCode === FtpError.EOF) {
          return { entries }; // normal end-of-listing
        }
        if (errCode === FtpError.FileNotFound) {
          return entries.length > 0 ? { entries } : { error: 'FileNotFound' };
        }
        const name = FTP_ERROR_NAMES[errCode] ?? `code=${errCode}`;
        this.log('warn', `FTP: ListDirectory ${path} NAK: ${name}`);
        return { error: name };
      }

      if (resp.opcode !== FtpOpcode.Ack) {
        return { error: `unexpected opcode ${resp.opcode}` };
      }

      // Parse the packed entries. The Ack payload uses `size` as the number
      // of valid bytes in `data` (not the count of entries).
      const buf = resp.data.slice(0, resp.size);
      let parsed = 0;
      let i = 0;
      while (i < buf.length) {
        // Find next null terminator
        let end = i;
        while (end < buf.length && buf[end] !== 0) end++;
        if (end === i) {
          // Empty entry (just \0) - skip
          i = end + 1;
          continue;
        }
        const tag = String.fromCharCode(buf[i] ?? 0);
        const body = new TextDecoder().decode(buf.slice(i + 1, end));
        if (tag === 'F') {
          // "name\tsize"
          const tabIdx = body.indexOf('\t');
          const name = tabIdx >= 0 ? body.slice(0, tabIdx) : body;
          const sizeStr = tabIdx >= 0 ? body.slice(tabIdx + 1) : '0';
          const size = parseInt(sizeStr, 10);
          if (!seenNames.has(name)) {
            seenNames.add(name);
            entries.push({ kind: 'file', name, size: Number.isFinite(size) ? size : 0 });
          }
          parsed++;
        } else if (tag === 'D') {
          // POSIX-style "." and ".." are protocol noise from the SITL
          // backend - they aren't useful in a flat browser UI. Count them
          // toward `parsed` so the offset advances, but don't surface them.
          if (body !== '.' && body !== '..' && !seenNames.has(body)) {
            seenNames.add(body);
            entries.push({ kind: 'dir', name: body });
          }
          parsed++;
        } else if (tag === 'S') {
          // Skipped entry - count it toward offset so we advance, but don't
          // add it to the visible result.
          parsed++;
        } // unknown tags silently ignored
        i = end + 1;
      }

      // If the response carried zero parseable entries, abort the loop or
      // we'd spin forever requesting the same offset.
      if (parsed === 0) return { entries };
      totalParsed += parsed;
    }

    return { entries };
  }

  /**
   * Quick write probe. Tries OpenFileWO on a throwaway path with a short
   * timeout (no retries), then immediately closes the session. Used to
   * decide before a real upload whether FTP writes are even possible on
   * this FC, so we don't burn 40+ seconds on retries before showing the
   * manual-install fallback.
   *
   * Returns the structured ACK/NAK result. Caller should NOT keep the
   * session open - we terminate it before returning.
   */
  async probeWrite(path: string, timeoutMs: number = 1500): Promise<{ ok: boolean; error?: string }> {
    // Don't disturb prior session state.
    const pathBytes = new TextEncoder().encode(path);
    const data = new Uint8Array(pathBytes.length + 1);
    data.set(pathBytes);

    // Single-shot send with a custom short timeout - no retries.
    const result = await this.sendRequestWithTimeout({
      opcode: FtpOpcode.OpenFileWO,
      session: 0,
      size: pathBytes.length,
      offset: 0,
      data,
    }, timeoutMs);

    if (!result) return { ok: false, error: 'no response (timed out)' };
    if (result.opcode === FtpOpcode.Ack) {
      // Session opened - free it immediately, we don't actually want to write.
      this.sessionId = result.session;
      try { await this.terminateSession(); } catch { /* ignore */ }
      return { ok: true };
    }
    if (result.opcode === FtpOpcode.Nak) {
      const errCode = result.data[0];
      return { ok: false, error: FTP_ERROR_NAMES[errCode ?? 0] ?? `code=${errCode}` };
    }
    return { ok: false, error: `unexpected opcode ${result.opcode}` };
  }

  /** Like sendRequest but with a per-call timeout override (for the probe). */
  private sendRequestWithTimeout(fields: {
    opcode: number;
    session: number;
    size: number;
    offset: number;
    data: Uint8Array;
  }, timeoutMs: number): Promise<FtpPayload | null> {
    return new Promise<FtpPayload | null>((resolve) => {
      this.clearPending();
      this.pendingResolve = resolve;
      this.pendingTimer = setTimeout(() => {
        this.pendingTimer = null;
        const r = this.pendingResolve;
        this.pendingResolve = null;
        r?.(null);
      }, timeoutMs);
      const payload = this.buildPayload(fields);
      this.sendPacket(payload).catch(() => {
        if (this.pendingTimer) {
          clearTimeout(this.pendingTimer);
          this.pendingTimer = null;
        }
        const r = this.pendingResolve;
        this.pendingResolve = null;
        r?.(null);
      });
    });
  }

  /**
   * Upload a file to the FC's virtual filesystem.
   * Performs CreateFile → repeated WriteFile chunks → TerminateSession.
   * Returns the structured result so the caller can surface the precise
   * failure reason to the user (rather than just "FTP failed").
   *
   * The flight controller will overwrite an existing file at `path` on
   * CreateFile (per the MAVLink FTP spec). Use a unique filename to avoid
   * stomping unrelated user files.
   *
   * Speed: defaults to 239-byte chunks (max for MAVLink v1 FTP) - much faster
   * than 110-byte read chunks since the request/response loop is the bottleneck.
   * Tested at ~12-25 KB/s over USB-CDC and TCP localhost.
   */
  async uploadFile(
    path: string,
    contents: Uint8Array,
    progress?: FtpProgressCallback,
  ): Promise<{ ok: boolean; error?: string }> {
    try {
      await this.resetSessions();

      // Try OpenFileWO first (O_WRONLY|O_CREAT, no truncate). Mission Planner
      // uses this for script uploads and ArduPilot's POSIX backend handles it
      // reliably even when /APM/scripts/ already contains stale state.
      // CreateFile (O_WRONLY|O_CREAT|O_TRUNC) is the spec-blessed alternative
      // but some ArduPilot builds return generic "Fail" from it.
      //
      // We deliberately do NOT call CreateDirectory/RemoveFile beforehand:
      // some ArduPilot SITL builds silently drop unsupported opcodes which
      // wedges the FTP server's per-session state, causing every subsequent
      // request to time out. Keep the request sequence as short as possible.
      let opened = await this.openFileWO(path);
      if (!opened.ok) {
        this.log('debug', `FTP: OpenFileWO rejected (${opened.error}) - trying CreateFile fallback`);
        opened = await this.createFile(path);
      }
      if (!opened.ok) {
        const msg = `Could not open ${path} for write: OpenFileWO/CreateFile both rejected (${opened.error ?? 'unknown'}). The /APM/scripts/ directory may not exist on this FC - on SITL, create it in the working directory before launch.`;
        this.log('warn', `FTP: ${msg}`);
        return { ok: false, error: msg };
      }

      // Sequentially write each chunk. Use the maximum FTP v1 payload (239 B)
      // because the round-trip per chunk dominates - cutting chunks in half
      // doubles the upload time, since each request must wait for an ACK.
      const totalBytes = contents.length;
      const chunkSize = FTP_WRITE_SIZE;
      let offset = 0;
      progress?.(0, totalBytes); // initial 0% so the UI doesn't sit empty

      while (offset < totalBytes) {
        const slice = contents.subarray(offset, Math.min(offset + chunkSize, totalBytes));
        const result = await this.writeFileChunk(offset, slice);
        if (!result.ok) {
          const msg = `WriteFile rejected (${result.error ?? 'unknown'}) at offset ${offset}/${totalBytes}`;
          this.log('warn', `FTP: ${msg}`);
          try { await this.terminateSession(); } catch { /* ignore */ }
          return { ok: false, error: msg };
        }
        offset += slice.length;
        progress?.(offset, totalBytes);
      }

      try { await this.terminateSession(); } catch { /* ignore */ }
      return { ok: true };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      this.log('error', `FTP: upload exception for ${path}: ${msg}`);
      try { await this.terminateSession(); } catch { /* ignore */ }
      return { ok: false, error: msg };
    }
  }

  // ─── Upload internals ────────────────────────────────────────────────────

  /**
   * Best-effort: create every directory along the path leading up to the
   * final filename. Each CreateDirectory NAK is tolerated - 'FileExists'
   * means the dir already exists, anything else and we let CreateFile surface
   * the underlying error with full context.
   */
  private async ensureParentDirectories(path: string): Promise<void> {
    // Strip filename, then split into ancestor segments.
    const lastSlash = path.lastIndexOf('/');
    if (lastSlash <= 0) return;
    const dirPath = path.slice(0, lastSlash);
    const segments = dirPath.split('/').filter(Boolean);
    let cumulative = '';
    for (const seg of segments) {
      cumulative += `/${seg}`;
      const result = await this.createDirectory(cumulative);
      if (!result.ok) {
        // FileExists is the expected case for already-present directories.
        // Anything else is unexpected - bump to warn so we can see it in the
        // user-facing console (debug is filtered by default).
        const errLower = (result.error ?? '').toLowerCase();
        if (errLower.includes('exists')) {
          this.log('debug', `FTP: CreateDirectory ${cumulative} - already exists (ok)`);
        } else {
          this.log('warn', `FTP: CreateDirectory ${cumulative} -> ${result.error ?? 'unknown'} (continuing anyway)`);
        }
      } else {
        this.log('debug', `FTP: CreateDirectory ${cumulative} - created`);
      }
    }
  }

  /**
   * Remove a file at `path`. Returns ok on ACK or FileNotFound (idempotent),
   * not-ok on real errors (permission, busy, etc). Public so the file
   * browser can offer delete; also used internally as a pre-step before
   * CreateFile to ensure clean state.
   */
  async removeFile(path: string): Promise<{ ok: boolean; error?: string }> {
    const pathBytes = new TextEncoder().encode(path);
    const data = new Uint8Array(pathBytes.length + 1);
    data.set(pathBytes);
    const resp = await this.sendRequest({
      opcode: FtpOpcode.RemoveFile,
      session: 0,
      size: pathBytes.length,
      offset: 0,
      data,
    });
    if (!resp) return { ok: false, error: 'no response (timed out)' };
    if (resp.opcode === FtpOpcode.Ack) return { ok: true };
    if (resp.opcode === FtpOpcode.Nak) {
      const errCode = resp.data[0];
      if (errCode === FtpError.FileNotFound) return { ok: true };
      return { ok: false, error: FTP_ERROR_NAMES[errCode ?? 0] ?? `code=${errCode}` };
    }
    return { ok: false, error: `unexpected opcode ${resp.opcode}` };
  }

  /**
   * Remove an empty directory at `path`. Returns ok on ACK or FileNotFound;
   * NAK with Fail/FailErrno typically means the directory is non-empty (the
   * MAVLink-FTP spec does not define a dedicated "not empty" error code,
   * so the caller should surface the raw error to the user).
   */
  async removeDirectory(path: string): Promise<{ ok: boolean; error?: string }> {
    const pathBytes = new TextEncoder().encode(path);
    const data = new Uint8Array(pathBytes.length + 1);
    data.set(pathBytes);
    const resp = await this.sendRequest({
      opcode: FtpOpcode.RemoveDirectory,
      session: 0,
      size: pathBytes.length,
      offset: 0,
      data,
    });
    if (!resp) return { ok: false, error: 'no response (timed out)' };
    if (resp.opcode === FtpOpcode.Ack) return { ok: true };
    if (resp.opcode === FtpOpcode.Nak) {
      const errCode = resp.data[0];
      if (errCode === FtpError.FileNotFound) return { ok: true };
      return { ok: false, error: FTP_ERROR_NAMES[errCode ?? 0] ?? `code=${errCode}` };
    }
    return { ok: false, error: `unexpected opcode ${resp.opcode}` };
  }

  /**
   * Rename or move a file/directory from `oldPath` to `newPath`. Per the
   * MAVLink-FTP spec the data field is `<old>\0<new>\0` and `size` is the
   * total payload byte count. ArduPilot supports rename across directories
   * on the same filesystem; cross-filesystem moves return Fail.
   */
  async rename(oldPath: string, newPath: string): Promise<{ ok: boolean; error?: string }> {
    const enc = new TextEncoder();
    const oldBytes = enc.encode(oldPath);
    const newBytes = enc.encode(newPath);
    const data = new Uint8Array(oldBytes.length + 1 + newBytes.length + 1);
    data.set(oldBytes, 0);
    data[oldBytes.length] = 0;
    data.set(newBytes, oldBytes.length + 1);
    data[oldBytes.length + 1 + newBytes.length] = 0;
    const resp = await this.sendRequest({
      opcode: FtpOpcode.Rename,
      session: 0,
      size: data.length,
      offset: 0,
      data,
    });
    if (!resp) return { ok: false, error: 'no response (timed out)' };
    if (resp.opcode === FtpOpcode.Ack) return { ok: true };
    if (resp.opcode === FtpOpcode.Nak) {
      const errCode = resp.data[0];
      return { ok: false, error: FTP_ERROR_NAMES[errCode ?? 0] ?? `code=${errCode}` };
    }
    return { ok: false, error: `unexpected opcode ${resp.opcode}` };
  }

  /**
   * Open file for write (O_WRONLY | O_CREAT, no O_TRUNC). Mission Planner
   * uses this for script uploads. Some ArduPilot filesystem backends accept
   * OpenFileWO when CreateFile fails with the generic "Fail" code.
   */
  private async openFileWO(path: string): Promise<{ ok: boolean; error?: string }> {
    const pathBytes = new TextEncoder().encode(path);
    const data = new Uint8Array(pathBytes.length + 1);
    data.set(pathBytes);

    let lastErr: string | undefined;
    for (let retry = 0; retry < FTP_MAX_RETRIES; retry++) {
      const resp = await this.sendRequest({
        opcode: FtpOpcode.OpenFileWO,
        session: 0,
        size: pathBytes.length,
        offset: 0,
        data,
      });
      if (!resp) { lastErr = 'no response (timed out)'; continue; }
      if (resp.opcode === FtpOpcode.Ack) {
        this.sessionId = resp.session;
        return { ok: true };
      }
      if (resp.opcode === FtpOpcode.Nak) {
        const errCode = resp.data[0];
        const name = FTP_ERROR_NAMES[errCode ?? 0] ?? `code=${errCode}`;
        if (errCode === FtpError.NoSessionsAvailable) {
          await this.resetSessions();
          lastErr = name;
          continue;
        }
        return { ok: false, error: name };
      }
    }
    return { ok: false, error: lastErr ?? 'no ACK after retries' };
  }

  private async createDirectory(path: string): Promise<{ ok: boolean; error?: string }> {
    const pathBytes = new TextEncoder().encode(path);
    const data = new Uint8Array(pathBytes.length + 1);
    data.set(pathBytes); // null-terminated

    const resp = await this.sendRequest({
      opcode: FtpOpcode.CreateDirectory,
      session: 0,
      size: pathBytes.length,
      offset: 0,
      data,
    });

    if (!resp) return { ok: false, error: 'no response (timed out)' };
    if (resp.opcode === FtpOpcode.Ack) return { ok: true };
    if (resp.opcode === FtpOpcode.Nak) {
      const errCode = resp.data[0];
      return { ok: false, error: FTP_ERROR_NAMES[errCode ?? 0] ?? `code=${errCode}` };
    }
    return { ok: false, error: `unexpected opcode ${resp.opcode}` };
  }

  private async createFile(path: string): Promise<{ ok: boolean; error?: string }> {
    const pathBytes = new TextEncoder().encode(path);
    const data = new Uint8Array(pathBytes.length + 1);
    data.set(pathBytes); // null-terminated

    let lastErr: string | undefined;
    for (let retry = 0; retry < FTP_MAX_RETRIES; retry++) {
      const resp = await this.sendRequest({
        opcode: FtpOpcode.CreateFile,
        session: 0,
        size: pathBytes.length,
        offset: 0,
        data,
      });

      if (!resp) {
        lastErr = 'no response (timed out)';
        this.log('debug', `FTP: CreateFile timeout (attempt ${retry + 1}/${FTP_MAX_RETRIES})`);
        continue;
      }

      if (resp.opcode === FtpOpcode.Ack) {
        this.sessionId = resp.session;
        return { ok: true };
      }

      if (resp.opcode === FtpOpcode.Nak) {
        const errCode = resp.data[0];
        const name = FTP_ERROR_NAMES[errCode ?? 0] ?? `code=${errCode}`;
        if (errCode === FtpError.NoSessionsAvailable) {
          this.log('debug', `FTP: CreateFile NAK NoSessionsAvailable - resetting sessions and retrying`);
          await this.resetSessions();
          lastErr = name;
          continue;
        }
        return { ok: false, error: name };
      }
    }
    return { ok: false, error: lastErr ?? 'no ACK after retries' };
  }

  private async writeFileChunk(offset: number, data: Uint8Array): Promise<{ ok: boolean; error?: string }> {
    let lastErr: string | undefined;
    for (let retry = 0; retry < FTP_MAX_RETRIES; retry++) {
      const resp = await this.sendRequest({
        opcode: FtpOpcode.WriteFile,
        session: this.sessionId,
        size: data.length,
        offset,
        data,
      });

      if (!resp) {
        lastErr = 'no response (timed out)';
        continue;
      }

      if (resp.opcode === FtpOpcode.Ack) {
        return { ok: true };
      }

      if (resp.opcode === FtpOpcode.Nak) {
        const errCode = resp.data[0];
        const name = FTP_ERROR_NAMES[errCode ?? 0] ?? `code=${errCode}`;
        return { ok: false, error: name };
      }
    }
    return { ok: false, error: lastErr ?? 'no ACK after retries' };
  }

  // ─── Download Logic ──────────────────────────────────────────────────────

  /**
   * Sequential download: send ReadFile, wait for ACK, advance offset, repeat.
   * Simple and reliable. Fast on USB serial (<1ms round-trip per chunk).
   */
  private async sequentialDownload(
    fileSize: number,
    progress?: FtpProgressCallback,
  ): Promise<Uint8Array | null> {
    const result = new Uint8Array(fileSize);
    let offset = 0;

    while (offset < fileSize) {
      const remaining = fileSize - offset;
      const chunkSize = Math.min(this.readSize, remaining);

      const chunk = await this.readFileChunk(offset, chunkSize);
      if (!chunk) {
        this.log('warn', `FTP: read failed at offset ${offset}/${fileSize}`);
        return null;
      }

      // chunk may be shorter than requested (near end of file)
      if (chunk.length === 0) break;

      result.set(chunk, offset);
      offset += chunk.length;

      if (progress) {
        progress(offset, fileSize);
      }
    }

    return result;
  }

  // ─── Low-level Protocol ──────────────────────────────────────────────────

  private async resetSessions(): Promise<void> {
    const resp = await this.sendRequest({
      opcode: FtpOpcode.ResetSessions,
      session: 0,
      size: 0,
      offset: 0,
      data: new Uint8Array(0),
    });

    if (resp && resp.opcode === FtpOpcode.Nak) {
      const errCode = resp.data[0];
      if (errCode !== FtpError.UnknownCommand) {
        this.log('debug', `FTP: ResetSessions NAK: ${FTP_ERROR_NAMES[errCode ?? 0] ?? 'unknown'}`);
      }
    }
  }

  private async openFileRO(path: string): Promise<number | null> {
    const pathBytes = new TextEncoder().encode(path);
    const data = new Uint8Array(pathBytes.length + 1); // null-terminated
    data.set(pathBytes);

    for (let retry = 0; retry < FTP_MAX_RETRIES; retry++) {
      const resp = await this.sendRequest({
        opcode: FtpOpcode.OpenFileRO,
        session: 0,
        size: pathBytes.length,
        offset: 0,
        data,
      });

      if (!resp) {
        this.log('debug', `FTP: OpenFileRO timeout (attempt ${retry + 1}/${FTP_MAX_RETRIES})`);
        continue;
      }

      if (resp.opcode === FtpOpcode.Ack) {
        this.sessionId = resp.session;
        const view = new DataView(resp.data.buffer, resp.data.byteOffset, resp.data.byteLength);
        return view.getUint32(0, true);
      }

      if (resp.opcode === FtpOpcode.Nak) {
        const errCode = resp.data[0];
        if (errCode === FtpError.FileNotFound || errCode === FtpError.UnknownCommand) {
          return null;
        }
        if (errCode === FtpError.NoSessionsAvailable) {
          await this.resetSessions();
          continue;
        }
        this.log('debug', `FTP: OpenFileRO NAK: ${FTP_ERROR_NAMES[errCode ?? 0] ?? 'unknown'}`);
      }
    }

    return null;
  }

  private async readFileChunk(offset: number, size: number): Promise<Uint8Array | null> {
    for (let retry = 0; retry < FTP_MAX_RETRIES; retry++) {
      const resp = await this.sendRequest({
        opcode: FtpOpcode.ReadFile,
        session: this.sessionId,
        size,
        offset,
        data: new Uint8Array(0),
      });

      if (!resp) continue;

      if (resp.opcode === FtpOpcode.Ack) {
        return resp.data.slice(0, resp.size);
      }

      if (resp.opcode === FtpOpcode.Nak) {
        const errCode = resp.data[0];
        if (errCode === FtpError.EOF) {
          return new Uint8Array(0);
        }
        this.log('debug', `FTP: ReadFile NAK at offset ${offset}: ${FTP_ERROR_NAMES[errCode ?? 0] ?? 'unknown'}`);
      }
    }
    return null;
  }

  private async terminateSession(): Promise<void> {
    await this.sendRequest({
      opcode: FtpOpcode.TerminateSession,
      session: this.sessionId,
      size: 0,
      offset: 0,
      data: new Uint8Array(0),
    });
  }

  // ─── Request/Response ────────────────────────────────────────────────────

  private sendRequest(fields: {
    opcode: number;
    session: number;
    size: number;
    offset: number;
    data: Uint8Array;
  }): Promise<FtpPayload | null> {
    return new Promise<FtpPayload | null>((resolve) => {
      this.clearPending();

      this.pendingResolve = resolve;

      this.pendingTimer = setTimeout(() => {
        this.pendingTimer = null;
        const r = this.pendingResolve;
        this.pendingResolve = null;
        r?.(null);
      }, FTP_TIMEOUT_MS);

      const payload = this.buildPayload(fields);
      this.sendPacket(payload).catch(() => {
        if (this.pendingTimer) {
          clearTimeout(this.pendingTimer);
          this.pendingTimer = null;
        }
        const r = this.pendingResolve;
        this.pendingResolve = null;
        r?.(null);
      });
    });
  }

  private buildPayload(fields: {
    opcode: number;
    session: number;
    size: number;
    offset: number;
    data: Uint8Array;
  }): Uint8Array {
    this.seqNumber = (this.seqNumber + 1) & 0xffff;

    return serializeFtpPayload({
      seqNumber: this.seqNumber,
      session: fields.session,
      opcode: fields.opcode,
      size: fields.size,
      reqOpcode: 0,
      burstComplete: 0,
      offset: fields.offset,
      data: fields.data,
    });
  }

  // ─── Helpers ─────────────────────────────────────────────────────────────

  private clearPending(): void {
    if (this.pendingTimer) {
      clearTimeout(this.pendingTimer);
      this.pendingTimer = null;
    }
    if (this.pendingResolve) {
      this.pendingResolve(null);
      this.pendingResolve = null;
    }
  }
}
