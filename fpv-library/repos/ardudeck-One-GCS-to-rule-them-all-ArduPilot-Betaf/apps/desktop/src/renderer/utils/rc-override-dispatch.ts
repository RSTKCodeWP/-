/**
 * Decide how to transmit an RC override for the current link. MAVLink and MSP
 * use completely different messages, so the flight-control store must dispatch
 * on the connection protocol rather than assuming MSP.
 *
 *  - MAVLink -> RC_CHANNELS_OVERRIDE, driving RC1..RC4 (Roll/Pitch/Throttle/Yaw).
 *    Aux channels are left "ignore" by the main handler so we never hijack
 *    FLTMODE_CH.
 *  - anything else (MSP/Betaflight/iNAV) -> MSP_SET_RAW_RC with the full array.
 */

export type RcOverrideCall =
  | { kind: 'mavlink'; roll: number; pitch: number; throttle: number; yaw: number }
  | { kind: 'msp'; channels: number[] };

export function rcOverrideCall(protocol: string | undefined, channels: number[]): RcOverrideCall {
  if (protocol === 'mavlink') {
    return {
      kind: 'mavlink',
      roll: channels[0] ?? 1500,
      pitch: channels[1] ?? 1500,
      throttle: channels[2] ?? 1000,
      yaw: channels[3] ?? 1500,
    };
  }
  return { kind: 'msp', channels };
}
