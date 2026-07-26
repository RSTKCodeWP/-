import type { TeamEmconConfig } from "./config.js";

export type Side = "BLUFOR" | "OPFOR";
export type EventSide = Side | "SYS";

export interface Vec2 { x: number; y: number; }

/* One DF intercept: sensor position, noisy bearing, 1-sigma, sim time. */
export interface Measurement {
  sx: number;
  sy: number;
  brg: number;
  sig: number;
  t: number;
}

export interface DfNode {
  id: string;
  x: number;
  y: number;
  det: number;             // C2 uplink intercept count
  lastBrg: number | null;
  lastT: number;
  dl: number;              // video downlink intercept count
}

export interface Gcs {
  id: string;
  x: number;
  y: number;
  destroyed: boolean;
  transmitting: boolean;
}

export type DroneState =
  | "STANDBY" | "TRANSIT" | "HOLD" | "COMMIT" | "TERMINAL"
  | "IMPACT" | "LINK LOST" | "DOWN";

export interface Drone {
  id: string;
  side: Side;
  x: number;
  y: number;
  agl: number;
  hdg: number;
  spd: number;
  state: DroneState;
  launched: boolean;
  airT: number;
  batt: number;
  wps: Vec2[];
  videoOn: boolean;
  downed: boolean;
  linkLost: boolean;
  linkLostT: number;
  orbitA: number;
  fixReached: boolean;
  searchR: number;
}

/* Least-squares fix estimate. Solved estimates carry the full quality
   breakdown; unsolved ones only the placeholder fields. */
export interface Estimate {
  p: Vec2 | null;
  cep: number;             // effective CEP = max(formal, geometry-penalized, jitter)
  s1: number;              // error-ellipse semi-axis sigmas
  s2: number;
  ang: number;             // ellipse orientation, math frame
  solved: boolean;
  formalCep?: number;
  geomCep?: number;
  jitter?: number;
  cutDeg?: number;
  balance?: number;
}

export interface TeamFlags {
  firstLOB: boolean;
  crossFix: boolean;
  fixed: boolean;
  committed: boolean;
  acquired: boolean;
  dlFirst: boolean;
  lowBatt: boolean;
  onStation: boolean;
}

/* Sim times at which each flag was first set (headless addition — the
   browser version derives these from the event log text). */
export type FlagTimes = Partial<Record<keyof TeamFlags, number>>;

export interface SearchBox { x: number; y: number; w: number; h: number; }

export interface Team {
  side: Side;
  enemy: Side;
  emcon: TeamEmconConfig;
  emconLabel: string;
  launchT: number;
  ulPhase: number;
  viPhase: number;
  gcs: Gcs;
  nodes: DfNode[];
  drone: Drone;
  // Collection effort against the enemy GCS.
  meas: Measurement[];
  est: Estimate;
  estHist: { x: number; y: number; t: number }[];
  flags: TeamFlags;
  flagTimes: FlagTimes;
  droneTrack: { x: number; y: number; t: number } | null; // noisy track of enemy drone from DL intercepts
  searchBox: SearchBox;
  nai: string;
  holdPt: Vec2;
}

export interface SimEvent {
  t: number;
  side: EventSide;
  text: string;
}

export type OutcomeResult = Side | "STALEMATE";
export type OutcomeReason = "gcs_destroyed" | "both_drones_down" | "time_limit";
