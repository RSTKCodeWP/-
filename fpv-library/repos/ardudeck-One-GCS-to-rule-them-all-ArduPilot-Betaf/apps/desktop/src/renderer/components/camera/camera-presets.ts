/**
 * Built-in camera source presets.
 *
 * Defaults sourced from current (2025-2026) vendor docs. Port 8554 is the
 * de-facto RTSP standard across the serious payloads (SIYI / Herelink /
 * RunCam WiFiLink). URLs are editable after the preset is applied — these are
 * just the known-good starting points so the operator picks a payload instead
 * of typing a URL from memory.
 */

import type { CameraPreset } from '../../../shared/camera-types';

export const CAMERA_PRESETS: CameraPreset[] = [
  {
    id: 'mavlink',
    label: 'Advertised by vehicle (MAVLink)',
    kind: 'mavlink',
    note: 'Auto-discovers the stream URI from VIDEO_STREAM_INFORMATION. Falls back to manual if the vehicle never advertises one.',
  },
  {
    id: 'siyi-a8',
    label: 'SIYI A8 mini / ZR10 / ZR30',
    kind: 'rtsp',
    url: 'rtsp://192.168.144.25:8554/main.264',
    hfovDeg: 81,
    note: 'Camera + autopilot must share the 192.168.144.x subnet. Set the IP in SIYI Assistant.',
  },
  {
    id: 'siyi-zt6',
    label: 'SIYI ZT6 / ZT30 (RGB)',
    kind: 'rtsp',
    url: 'rtsp://192.168.144.25:8554/video2',
    hfovDeg: 81,
    note: 'Multi-sensor cams expose /video1 (IR) and /video2 (RGB).',
  },
  {
    id: 'herelink',
    label: 'Herelink (ground unit)',
    kind: 'rtsp',
    url: 'rtsp://192.168.43.1:8554/fpv_stream',
    note: 'WiFi hotspot mode. USB-tether uses 192.168.42.129; station mode uses the assigned IP.',
  },
  {
    id: 'runcam-wifilink',
    label: 'RunCam WiFiLink / OpenIPC (wfb-ng)',
    kind: 'wfbng',
    url: 'udp://0.0.0.0:5600',
  },
  {
    id: 'rubyfpv',
    label: 'RubyFPV (relayed video)',
    kind: 'rubyfpv',
    url: 'udp://127.0.0.1:5600',
    note: 'Enable "video forwarding to local network" in RubyFPV. The engine bridges its raw H.264/UDP into the hub.',
  },
  {
    id: 'rtsp',
    label: 'Custom RTSP URL',
    kind: 'rtsp',
    url: 'rtsp://',
    note: 'Any RTSP source. The hub republishes it as low-latency WebRTC.',
  },
  {
    id: 'rtp-udp',
    label: 'Custom RTP / UDP (H.264)',
    kind: 'rtp-udp',
    url: 'udp://0.0.0.0:5600',
    note: 'Raw H.264 over UDP, e.g. a companion-computer GStreamer pipeline.',
  },
  {
    id: 'srt',
    label: 'Custom SRT',
    kind: 'srt',
    url: 'srt://0.0.0.0:8890?mode=listener',
    note: 'Higher latency than RTP but resilient over lossy long-haul links.',
  },
  {
    id: 'webrtc',
    label: 'Custom WebRTC (WHEP)',
    kind: 'webrtc',
    url: 'https://',
    note: 'A WHEP endpoint published by a companion computer. Lowest latency, played directly.',
  },
  {
    id: 'uvc',
    label: 'USB / HDMI capture device',
    kind: 'uvc',
    note: 'Analog-FPV-to-USB dongle or capture card on this machine. Played locally — the only path suitable for piloting.',
  },
];

export function presetById(id: string): CameraPreset | undefined {
  return CAMERA_PRESETS.find((p) => p.id === id);
}
