/*
 * fpv-sim headless engine — public API.
 *
 * Extracted from https://github.com/wasomma/fpv-sim (index.html) with
 * simulation behavior preserved exactly: the same seed produces the same
 * engagement, tick for tick, as the browser version. All data is notional.
 */

export { Simulation, runEngagement, MAX_SIM_S_DEFAULT } from "./simulation.js";
export type {
  EngagementResult, TeamResult, TeamFixResult, TeamNodeResult, PhaseChange, RunOptions,
} from "./simulation.js";
export {
  DEFAULT_CONFIG, DEFAULT_SEED, mergeConfig, emconLabel,
} from "./config.js";
export type {
  SimConfig, ConfigOverrides, DroneConfig, CuasConfig, FixConfig, TeamEmconConfig, EmconLabel,
} from "./config.js";
export { aggregateSweep, comparePaired, distribution } from "./aggregate.js";
export type { SweepSummary, PairedComparison, DistributionStats } from "./aggregate.js";
export { computeEstimate, updateFix } from "./fix.js";
export type { FixSolution } from "./fix.js";
export { mulberry32, makeGauss } from "./rng.js";
export type { Rng } from "./rng.js";
export { buildWorld, elevAt, canopyAt } from "./terrain.js";
export type { World } from "./terrain.js";
export { pathAtten } from "./rf.js";
export type {
  Side, EventSide, SimEvent, Team, Drone, DfNode, Gcs, Measurement, Estimate,
  OutcomeResult, OutcomeReason, Vec2,
} from "./types.js";
