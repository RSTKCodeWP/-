import { describe, it, expect } from 'vitest';
import { resolveStreamUrl } from './useCameraStream';
import type { CameraSourceConfig } from '../../../shared/camera-types';

function src(kind: CameraSourceConfig['kind'], url?: string): CameraSourceConfig {
  return { id: 'x', vehicleKey: 'v', kind, label: kind, ...(url ? { url } : {}) };
}

describe('resolveStreamUrl', () => {
  it('uses the advertised MAVLink URI for mavlink sources', () => {
    expect(resolveStreamUrl(src('mavlink'), 'rtsp://cam/adv')).toBe('rtsp://cam/adv');
  });

  it('ignores the advertised URI for non-mavlink sources', () => {
    expect(resolveStreamUrl(src('rtsp', 'rtsp://x/a'), 'rtsp://cam/adv')).toBe('rtsp://x/a');
  });

  it('returns undefined when a mavlink source has no advertised URI yet', () => {
    expect(resolveStreamUrl(src('mavlink'), undefined)).toBeUndefined();
  });
});
