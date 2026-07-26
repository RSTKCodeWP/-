/**
 * @module video/webrtc/recording
 * @description MediaRecorder bindings + canvas-based screenshot
 * capture. Each function reads the active video element from the
 * shared session-state singleton.
 * @license GPL-3.0-only
 */

import { useVideoStore } from "@/stores/video-store";
import {
  clearRecordedChunks,
  getMediaRecorder,
  getRecordedChunks,
  getVideoElement,
  pushRecordedChunk,
  setMediaRecorder,
} from "./session-state";

/** Start recording the video stream to a local WebM file. */
export function startRecording(): void {
  const el = getVideoElement();
  if (!el?.srcObject) {
    throw new Error("No active stream to record");
  }

  const store = useVideoStore.getState();
  clearRecordedChunks();

  const stream = el.srcObject as MediaStream;
  const recorder = new MediaRecorder(stream, {
    mimeType: "video/webm;codecs=vp8,opus",
  });
  setMediaRecorder(recorder);

  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) pushRecordedChunk(e.data);
  };

  recorder.start(1000); // 1-second chunks
  store.setRecording(true);
}

/** Stop recording and download the file. */
export function stopRecording(): Blob | null {
  const store = useVideoStore.getState();
  const recorder = getMediaRecorder();

  if (!recorder || recorder.state === "inactive") {
    store.setRecording(false);
    return null;
  }

  recorder.stop();
  store.setRecording(false);

  const blob = new Blob(getRecordedChunks(), { type: "video/webm" });
  clearRecordedChunks();
  setMediaRecorder(null);

  // Auto-download
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `altnautica-recording-${Date.now()}.webm`;
  a.click();
  URL.revokeObjectURL(url);

  return blob;
}

/** Capture a screenshot from the current video frame. */
export function captureScreenshot(): string | null {
  const el = getVideoElement();
  if (!el || el.readyState < 2) return null;

  const canvas = document.createElement("canvas");
  canvas.width = el.videoWidth;
  canvas.height = el.videoHeight;

  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  ctx.drawImage(el, 0, 0);
  const dataUrl = canvas.toDataURL("image/png");

  // Auto-download
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = `altnautica-screenshot-${Date.now()}.png`;
  a.click();

  return dataUrl;
}
