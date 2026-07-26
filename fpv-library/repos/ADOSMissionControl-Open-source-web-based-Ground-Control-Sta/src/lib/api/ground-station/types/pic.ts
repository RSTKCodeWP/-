/**
 * @module api/ground-station/types/pic
 * @description Pilot-in-Command arbiter types: state snapshot, claim /
 * release / confirm-token responses, and the streamed event envelope.
 *
 * @license GPL-3.0-only
 */

export interface PicState {
  state: string;
  claimed_by: string | null;
  claim_counter: number;
  primary_gamepad_id: string | null;
}

export interface PicClaimResult {
  claimed: boolean;
  claimed_by: string | null;
  claim_counter: number;
  requires_confirm_token?: boolean;
}

export interface PicReleaseResult {
  released: boolean;
  claimed_by: string | null;
}

export interface PicConfirmTokenResult {
  confirm_token: string;
  expires_in_s: number;
}

export type PicEvent =
  | { type: "claimed"; claimed_by: string | null; claim_counter: number }
  | { type: "released"; claimed_by: string | null }
  | { type: "gamepad_changed"; primary_gamepad_id: string | null }
  | { type: "state"; state: string; claimed_by: string | null; claim_counter: number; primary_gamepad_id: string | null }
  | { type: string; [key: string]: unknown };
