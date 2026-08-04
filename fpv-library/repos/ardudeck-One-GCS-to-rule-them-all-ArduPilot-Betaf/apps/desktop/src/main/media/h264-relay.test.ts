import { describe, it, expect } from 'vitest';
import { needsH264Relay, buildH264RelayArgs } from './h264-relay.js';

describe('h264 relay helpers', () => {
  it('relays only when no WebRTC-playable video track exists', () => {
    expect(needsH264Relay(['H264'])).toBe(false);
    expect(needsH264Relay(['H264', 'MPEG-4 Audio'])).toBe(false);
    expect(needsH264Relay(['VP9'])).toBe(false);
    expect(needsH264Relay(['AV1'])).toBe(false);
    expect(needsH264Relay(['H265'])).toBe(true);
    expect(needsH264Relay(['H265', 'MPEG-4 Audio'])).toBe(true);
    // Misdeclared SDP (old SIYI firmware): gortsplib ingests as Generic.
    expect(needsH264Relay(['Generic'])).toBe(true);
    // Both declared: WHEP can pick the H264 track, no relay needed.
    expect(needsH264Relay(['H265', 'H264'])).toBe(false);
    // Unknown track list: attempt playback as-is, never transcode on a guess.
    expect(needsH264Relay([])).toBe(false);
  });

  it('builds a low-latency tcp-to-tcp transcode command', () => {
    const args = buildH264RelayArgs('rtsp://127.0.0.1:8554/cam_x', 'rtsp://127.0.0.1:8554/cam_xh264');
    expect(args[args.indexOf('-i') + 1]).toBe('rtsp://127.0.0.1:8554/cam_x');
    expect(args[args.length - 1]).toBe('rtsp://127.0.0.1:8554/cam_xh264');
    expect(args).toContain('libx264');
    expect(args).toContain('zerolatency');
    expect(args).toContain('-an');
    expect(args).not.toContain('copy');
    // Both legs ride loopback TCP; UDP RTP listeners are disabled on the hub.
    expect(args.filter((a) => a === '-rtsp_transport')).toHaveLength(2);
  });
});
