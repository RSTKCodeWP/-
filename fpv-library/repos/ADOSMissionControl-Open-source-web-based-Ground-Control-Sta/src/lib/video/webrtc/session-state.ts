/**
 * @module video/webrtc/session-state
 * @description Single source of truth for the module-level WebRTC
 * singletons (`pc`, `videoElement`, `mediaRecorder`). Every per-flow
 * module imports the accessors here so HMR-induced re-evaluations
 * don't end up with stale parallel copies of the connection.
 * @license GPL-3.0-only
 */

let pc: RTCPeerConnection | null = null;
let videoElement: HTMLVideoElement | null = null;
let mediaRecorder: MediaRecorder | null = null;
let recordedChunks: Blob[] = [];

export function getPc(): RTCPeerConnection | null {
  return pc;
}

export function setPc(next: RTCPeerConnection | null): void {
  pc = next;
}

export function getVideoElement(): HTMLVideoElement | null {
  return videoElement;
}

export function setVideoElementRef(el: HTMLVideoElement | null): void {
  videoElement = el;
}

export function getMediaRecorder(): MediaRecorder | null {
  return mediaRecorder;
}

export function setMediaRecorder(next: MediaRecorder | null): void {
  mediaRecorder = next;
}

export function getRecordedChunks(): Blob[] {
  return recordedChunks;
}

export function pushRecordedChunk(chunk: Blob): void {
  recordedChunks.push(chunk);
}

export function clearRecordedChunks(): void {
  recordedChunks = [];
}
