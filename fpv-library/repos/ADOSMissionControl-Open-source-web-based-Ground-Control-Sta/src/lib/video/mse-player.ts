/**
 * @module MsePlayer
 * @description WebSocket to MediaSource Extensions player for cloud video streaming.
 * Connects to the configured video relay at `<relay>/ws/stream/{deviceId}` and
 * feeds fragmented MP4 data into a browser <video> element. The relay URL is
 * resolved from clientConfig with a managed default (see config/endpoints).
 * @license GPL-3.0-only
 */

import { OFFICIAL_VIDEO_RELAY_URL } from "@/lib/config/endpoints";

// captureStream() is not in standard TypeScript DOM types but is widely supported
declare global {
  interface HTMLVideoElement {
    captureStream(): MediaStream;
  }
}

const VIDEO_RELAY_URL_DEFAULT = OFFICIAL_VIDEO_RELAY_URL;

// Reconnect delay after a transport drop or a detected stall.
const RECONNECT_DELAY_MS = 3000;
// How often the playback-stall watchdog samples currentTime.
const STALL_CHECK_INTERVAL_MS = 1000;
// currentTime frozen for at least this long while the socket is open
// means the decoder has wedged; force a fresh connection.
const PLAYBACK_STALL_TIMEOUT_MS = 5000;

export class MsePlayer {
  private ws: WebSocket | null = null;
  private mediaSource: MediaSource | null = null;
  private sourceBuffer: SourceBuffer | null = null;
  private videoElement: HTMLVideoElement | null = null;
  private queue: ArrayBuffer[] = [];
  private deviceId: string = "";
  private videoRelayUrl: string = VIDEO_RELAY_URL_DEFAULT;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  // Playback-stall watchdog. Tracks currentTime advancement so a frozen
  // decoder (no socket close, no error event) still triggers a reconnect.
  private stallTimer: ReturnType<typeof setInterval> | null = null;
  private lastPlaybackTime = 0;
  private lastPlaybackAdvanceAt = 0;
  // Guards against overlapping reconnect attempts from multiple triggers
  // (ws close + sourceBuffer error + stall watchdog all firing at once).
  private reconnectScheduled = false;
  // Set while stop() is tearing the session down. A socket closed as part
  // of an intentional teardown must NOT schedule a reconnect, so every
  // reconnect trigger bails when this is set. Cleared by the next start().
  private tearingDown = false;

  // Recording state
  private recorder: MediaRecorder | null = null;
  private recordedChunks: Blob[] = [];

  start(deviceId: string, videoElement: HTMLVideoElement, videoRelayUrl?: string): void {
    this.stop();
    // A fresh session — clear the teardown latch that stop() set.
    this.tearingDown = false;
    this.deviceId = deviceId;
    this.videoElement = videoElement;
    if (videoRelayUrl) this.videoRelayUrl = videoRelayUrl;

    if (!("MediaSource" in window)) {
      console.warn("MSE not supported in this browser");
      return;
    }

    this.mediaSource = new MediaSource();
    videoElement.src = URL.createObjectURL(this.mediaSource);

    this.mediaSource.addEventListener("sourceopen", () => {
      this.connectWebSocket();
    });

    this.startStallWatchdog();
  }

  /**
   * Poll currentTime while the socket is open. If playback has not
   * advanced within the timeout, the decoder has stalled silently (the
   * relay can keep the socket open and keep sending bytes that the
   * decoder refuses) — reconnect from scratch instead of waiting for an
   * onclose that never comes.
   */
  private startStallWatchdog(): void {
    if (this.stallTimer) return;
    this.lastPlaybackAdvanceAt = Date.now();
    this.lastPlaybackTime = this.videoElement?.currentTime ?? 0;
    this.stallTimer = setInterval(() => {
      const video = this.videoElement;
      // Only judge a stall while the socket is open. A closed socket has
      // its own reconnect path; a paused/backgrounded tab should not be
      // treated as a failure.
      if (!video || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
        this.lastPlaybackAdvanceAt = Date.now();
        return;
      }
      if (video.paused) {
        this.lastPlaybackAdvanceAt = Date.now();
        return;
      }
      const now = Date.now();
      if (video.currentTime > this.lastPlaybackTime) {
        this.lastPlaybackTime = video.currentTime;
        this.lastPlaybackAdvanceAt = now;
        return;
      }
      if (now - this.lastPlaybackAdvanceAt > PLAYBACK_STALL_TIMEOUT_MS) {
        this.scheduleReconnect();
      }
    }, STALL_CHECK_INTERVAL_MS);
  }

  /** Start recording the video stream to a .webm file. */
  startRecording(): boolean {
    if (!this.videoElement || this.recorder) return false;
    try {
      const stream = this.videoElement.captureStream();
      const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp9")
        ? "video/webm;codecs=vp9"
        : "video/webm";
      this.recorder = new MediaRecorder(stream, { mimeType });
      this.recordedChunks = [];
      this.recorder.ondataavailable = (e) => {
        if (e.data.size > 0) this.recordedChunks.push(e.data);
      };
      this.recorder.onstop = () => {
        const blob = new Blob(this.recordedChunks, { type: "video/webm" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
        a.href = url;
        a.download = `altnautica-recording-${ts}.webm`;
        a.click();
        URL.revokeObjectURL(url);
        this.recordedChunks = [];
        this.recorder = null;
      };
      this.recorder.start(1000);
      return true;
    } catch {
      return false;
    }
  }

  /** Stop recording and trigger download. */
  stopRecording(): void {
    if (this.recorder && this.recorder.state !== "inactive") {
      this.recorder.stop();
    }
  }

  /** Whether recording is currently active. */
  get isRecording(): boolean {
    return this.recorder !== null && this.recorder.state === "recording";
  }

  stop(): void {
    // Latch teardown so the imminent socket close does not bounce back
    // through scheduleReconnect(). reconnect() re-issues start(), which
    // clears the latch for the new session.
    this.tearingDown = true;
    this.stopRecording();
    if (this.stallTimer) {
      clearInterval(this.stallTimer);
      this.stallTimer = null;
    }
    this.reconnectScheduled = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      // Detach handlers BEFORE close() so the onclose teardown event does
      // not fire scheduleReconnect() on an intentional stop.
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;
      this.ws.onopen = null;
      this.ws.close();
      this.ws = null;
    }
    if (this.mediaSource && this.mediaSource.readyState === "open") {
      try {
        this.mediaSource.endOfStream();
      } catch { /* ignore */ }
    }
    this.mediaSource = null;
    this.sourceBuffer = null;
    this.queue = [];
    if (this.videoElement) {
      if (this.videoElement.src) {
        URL.revokeObjectURL(this.videoElement.src);
      }
      this.videoElement.src = "";
      this.videoElement = null;
    }
  }

  private connectWebSocket(): void {
    const url = `${this.videoRelayUrl}/ws/stream/${this.deviceId}`;
    this.ws = new WebSocket(url);
    this.ws.binaryType = "arraybuffer";

    this.ws.onopen = () => {
      // Fresh connection — reset the stall baseline and clear the
      // reconnect guard so a later failure can schedule again.
      this.reconnectScheduled = false;
      this.lastPlaybackAdvanceAt = Date.now();
      this.lastPlaybackTime = this.videoElement?.currentTime ?? 0;
    };

    this.ws.onmessage = (event) => {
      const data = event.data as ArrayBuffer;
      this.appendBuffer(data);
    };

    this.ws.onclose = () => {
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  /**
   * Debounced reconnect. Multiple triggers (socket close, sourceBuffer
   * error/abort, playback stall) can fire near-simultaneously; the guard
   * collapses them into a single fresh connection attempt.
   */
  private scheduleReconnect(): void {
    if (this.tearingDown || this.reconnectScheduled || !this.deviceId) return;
    this.reconnectScheduled = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      this.reconnect();
    }, RECONNECT_DELAY_MS);
  }

  /**
   * Tear the transport + MSE graph down and rebuild it. A frozen decoder
   * or an aborted sourceBuffer cannot be recovered in place, so we
   * recreate the MediaSource and re-open the socket from scratch.
   */
  private reconnect(): void {
    const video = this.videoElement;
    const deviceId = this.deviceId;
    const relayUrl = this.videoRelayUrl;
    if (!video || !deviceId) return;
    // stop() clears timers + tracks + nulls videoElement; re-issue start
    // with the captured references to rebuild the pipeline.
    this.stop();
    this.start(deviceId, video, relayUrl);
  }

  private appendBuffer(data: ArrayBuffer): void {
    if (!this.mediaSource || this.mediaSource.readyState !== "open") return;

    // Initialize source buffer on first data (fMP4 init segment)
    if (!this.sourceBuffer) {
      try {
        this.sourceBuffer = this.mediaSource.addSourceBuffer('video/mp4; codecs="avc1.640029"');
        this.sourceBuffer.addEventListener("updateend", () => {
          this.flushQueue();
        });
        // A sourceBuffer error or abort wedges the decode graph; neither
        // is recoverable by appending more data. Reconnect from scratch.
        this.sourceBuffer.addEventListener("error", () => {
          this.scheduleReconnect();
        });
        this.sourceBuffer.addEventListener("abort", () => {
          this.scheduleReconnect();
        });
      } catch {
        return;
      }
    }

    if (this.sourceBuffer.updating) {
      this.queue.push(data);
    } else {
      try {
        this.sourceBuffer.appendBuffer(data);
      } catch {
        this.queue.push(data);
      }
    }

    // Keep buffer trim -- remove data older than 10s
    if (this.videoElement && this.sourceBuffer && !this.sourceBuffer.updating) {
      const currentTime = this.videoElement.currentTime;
      if (currentTime > 10) {
        try {
          this.sourceBuffer.remove(0, currentTime - 5);
        } catch { /* ignore */ }
      }
    }
  }

  private flushQueue(): void {
    if (!this.sourceBuffer || this.sourceBuffer.updating || this.queue.length === 0) return;
    const next = this.queue.shift();
    if (next) {
      try {
        this.sourceBuffer.appendBuffer(next);
      } catch { /* ignore */ }
    }
  }
}
