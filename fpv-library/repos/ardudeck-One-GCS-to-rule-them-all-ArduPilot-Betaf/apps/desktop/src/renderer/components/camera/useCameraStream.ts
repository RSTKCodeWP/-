/**
 * Owns the playback lifecycle for one camera source and drives a <video>.
 *
 * Playback paths (identical to what the telemetry camera panel uses, so the OSD
 * tool and the panel render the exact same feed):
 *  - uvc      -> getUserMedia(deviceId), played locally (no engine)
 *  - webrtc/* -> main media engine returns a WHEP url; played over WebRTC
 * The engine normalizes rtsp/rtp/srt/rubyfpv into WHEP, so the renderer only
 * ever speaks getUserMedia or WHEP.
 */

import { useEffect, useRef, useState, type RefObject } from 'react';
import type { CameraSourceConfig } from '../../../shared/camera-types';
import { useCameraStore } from '../../stores/camera-store';
import { playWhep } from './whep';

export type CameraStreamStatus = 'starting' | 'live' | 'error';

/** The stream URL to hand the engine: mavlink resolves to the advertised URI. */
export function resolveStreamUrl(
  source: CameraSourceConfig,
  advertisedUri: string | undefined,
): string | undefined {
  return source.kind === 'mavlink' ? advertisedUri : source.url;
}

/**
 * Starts/stops the feed for `source` against `videoRef` and reports status.
 * Restarts only when a stream-relevant field changes — editing the label, HFOV
 * or low-latency flag must NOT tear down a live feed.
 */
export function useCameraStream(
  source: CameraSourceConfig,
  videoRef: RefObject<HTMLVideoElement>,
  onError?: (error: string) => void,
): { status: CameraStreamStatus; error: string | null } {
  const [status, setStatus] = useState<CameraStreamStatus>('starting');
  const [error, setError] = useState<string | null>(null);
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;
  const advertisedUri = useCameraStore((s) => s.videoStreams[source.vehicleKey]?.uri);

  useEffect(() => {
    let pc: RTCPeerConnection | null = null;
    let uvcStream: MediaStream | null = null;
    let cancelled = false;

    const fail = (msg: string) => {
      setStatus('error');
      setError(msg);
      onErrorRef.current?.(msg);
    };

    async function go() {
      setStatus('starting');
      setError(null);
      const video = videoRef.current;
      if (!video) return;
      try {
        if (source.kind === 'uvc') {
          uvcStream = await navigator.mediaDevices.getUserMedia({
            video: source.deviceId ? { deviceId: { exact: source.deviceId } } : true,
            audio: false,
          });
          if (cancelled) { uvcStream.getTracks().forEach((t) => t.stop()); return; }
          video.srcObject = uvcStream;
          await video.play().catch(() => {});
          setStatus('live');
          return;
        }

        const resolved = resolveStreamUrl(source, advertisedUri);
        const result = await window.electronAPI.cameraStart(source, resolved);
        if (cancelled) return;
        if (!result.ok || !result.session) {
          fail(result.error ?? 'Stream failed');
          return;
        }
        const playback = result.session.playback;
        if (playback.kind === 'webrtc') {
          pc = await playWhep(video, playback.whepUrl);
          if (cancelled) { pc.close(); return; }
          setStatus('live');
        } else if (playback.kind === 'uvc') {
          fail('Unexpected playback descriptor');
        }
      } catch (e) {
        if (cancelled) return;
        fail(e instanceof Error ? e.message : 'Playback error');
      }
    }
    void go();

    return () => {
      cancelled = true;
      if (pc) pc.close();
      if (uvcStream) uvcStream.getTracks().forEach((t) => t.stop());
      if (source.kind !== 'uvc') void window.electronAPI.cameraStop(source.id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source.id, source.kind, source.url, source.deviceId, source.rtspTransport, advertisedUri]);

  return { status, error };
}
