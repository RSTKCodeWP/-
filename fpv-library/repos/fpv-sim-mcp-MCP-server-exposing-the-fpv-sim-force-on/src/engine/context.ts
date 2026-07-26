/*
 * The mutable engagement context shared by the sensing, fix, and drone
 * modules. The Simulation class implements this interface; modules take it
 * as a parameter instead of reaching for the browser version's globals
 * (state / world / rng), which is the only structural change made to the
 * ported code paths.
 */

import type { SimConfig } from "./config.js";
import type { World } from "./terrain.js";
import type { Rng } from "./rng.js";
import type { EventSide, Side, Team } from "./types.js";

export interface SimCtx {
  readonly config: SimConfig;
  readonly world: World;
  readonly teams: Record<Side, Team>;
  t: number;
  winner: Side | null;
  endT: number | null;
  /* Single deterministic stream + its gaussian wrapper. Draw order matters. */
  readonly rng: Rng;
  readonly gauss: Rng;
  addEvent(side: EventSide, text: string): void;
}
