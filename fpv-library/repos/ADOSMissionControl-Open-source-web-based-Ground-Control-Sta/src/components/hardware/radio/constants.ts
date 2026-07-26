/**
 * @module hardware/radio/constants
 * @description Shared constants and small helpers for the WFB-ng radio
 * sub-panels. Pulled out so the per-section components don't have to
 * each redeclare the threshold and label values.
 * @license GPL-3.0-only
 */

import type {
  RadioTopology,
  RadioPeerLink,
  RadioHopState,
  RadioAcquireState,
} from "@/lib/api/ground-station/types";

export const POLL_INTERVAL_MS = 500;
export const PAIR_POLL_INTERVAL_MS = 2000;
export const EMPTY = "…";

// Threshold: RSSI green when at or above this many dBm.
export const RSSI_GREEN_DBM = -55;
// Threshold: RSSI yellow at or above this. Below this is red.
export const RSSI_YELLOW_DBM = -75;

// Brownout warning fires when host-VBUS topology is paired with TX
// power above the soft floor. The agent caps the slider at 15 dBm in
// this topology; the warning is informational.
export const BROWNOUT_TX_FLOOR_DBM = 12;

// Default safe-floor cap when the agent has not reported a per-driver
// maximum yet. The slider exposes this much head-room conservatively;
// agents that advertise a higher cap unlock more.
export const DEFAULT_TX_MAX_DBM = 15;

export function rssiClass(dbm: number | null): string {
  if (dbm == null) return "text-text-tertiary";
  if (dbm >= RSSI_GREEN_DBM) return "text-status-success";
  if (dbm >= RSSI_YELLOW_DBM) return "text-status-warning";
  return "text-status-error";
}

export function topologyClass(topology: RadioTopology): string {
  if (topology === "external_5v") return "border-status-success/40 text-status-success";
  if (topology === "powered_hub") return "border-accent-primary/40 text-accent-primary";
  return "border-border-default text-text-secondary";
}

// Badge color for the peer-rendezvous state. Linked is healthy, still
// searching is a warning (the link is up but the peer hasn't been heard
// yet), and no_peer is an error (radio is up, nothing on the other end).
export function peerLinkClass(peerLink: RadioPeerLink): string {
  if (peerLink === "linked") return "border-status-success/40 text-status-success";
  if (peerLink === "searching") return "border-status-warning/40 text-status-warning";
  return "border-status-error/40 text-status-error";
}

// Badge color for the hop supervisor state. Locked is healthy, hopping
// is a transient/info state, searching is a warning, idle is neutral.
export function hopStateClass(hopState: RadioHopState): string {
  if (hopState === "locked") return "border-status-success/40 text-status-success";
  if (hopState === "hopping") return "border-accent-primary/40 text-accent-primary";
  if (hopState === "searching") return "border-status-warning/40 text-status-warning";
  return "border-border-default text-text-secondary";
}

// Badge color for the ground receive acquirer state. Locked is healthy,
// searching is a warning (hunting for a valid channel), no-peer is an
// error (nothing heard from the other end), idle is neutral.
export function acquireStateClass(acquireState: RadioAcquireState): string {
  if (acquireState === "locked") return "border-status-success/40 text-status-success";
  if (acquireState === "searching") return "border-status-warning/40 text-status-warning";
  if (acquireState === "no-peer") return "border-status-error/40 text-status-error";
  return "border-border-default text-text-secondary";
}
