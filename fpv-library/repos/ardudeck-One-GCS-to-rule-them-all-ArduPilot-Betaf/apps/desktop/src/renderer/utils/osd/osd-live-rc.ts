/**
 * Pure helpers for the OSD Live panel's RC input display. Live RC comes from
 * telemetry (`telemetry-store.rcChannels`) — the actual sticks from the FC —
 * NOT the RC override output buffer.
 */

import type { RcChannelsData } from '../../../shared/telemetry-types';

/** First four channels are AETR (Roll/Pitch/Throttle/Yaw); the rest are CH5+. */
const PRIMARY_LABELS = ['Roll', 'Pitch', 'Thr', 'Yaw'];

export interface LiveRcRow {
  label: string;
  value: number;
  /** Throttle-style bar (fills from bottom/left) vs centred stick bar. */
  isThrottle: boolean;
}

/** Build the ordered channel rows to display from a live RC telemetry frame. */
export function buildLiveRcRows(rc: RcChannelsData): LiveRcRow[] {
  const count = rc.chancount > 0 ? rc.chancount : rc.channels.length;
  const rows: LiveRcRow[] = [];
  for (let i = 0; i < count; i++) {
    rows.push({
      label: PRIMARY_LABELS[i] ?? `CH${i + 1}`,
      value: rc.channels[i] ?? 0,
      isThrottle: i === 2, // channel 3 = throttle (AETR)
    });
  }
  return rows;
}

/**
 * RSSI as a 0-100 percentage, or null when unknown. MAVLink RC_CHANNELS uses
 * 0..254 scaled with 255 = invalid/unknown.
 */
export function rssiPercent(rssi: number): number | null {
  if (rssi >= 255 || rssi < 0) return null;
  return Math.round((rssi / 254) * 100);
}
