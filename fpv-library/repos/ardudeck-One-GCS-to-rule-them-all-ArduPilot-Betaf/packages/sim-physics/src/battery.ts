/**
 * Simple battery model: tracks state-of-charge and resting voltage, and sags
 * under load via internal resistance. Motor thrust scales with the delivered
 * voltage, so a depleting / sagging pack progressively loses authority - the
 * behaviour heavy-lift operators care about.
 */

export interface BatteryConfig {
  /** Pack voltage at full charge (V). */
  maxVoltage: number;
  /** Nominal/reference voltage the thrust model is calibrated at (V). */
  refVoltage: number;
  /** Capacity (Ah). <= 0 means an infinite pack (no SOC drain). */
  capacityAh: number;
  /** Internal resistance (ohm). Larger = more sag under current. */
  internalResistance: number;
  /** Approx hover current at refVoltage (A), used to estimate draw from thrust. */
  hoverCurrent: number;
  /** Thrust (N) at which `hoverCurrent` is drawn (i.e. weight at hover). */
  hoverThrust: number;
}

export interface BatteryState {
  /** Remaining charge (Ah). */
  remainingAh: number;
  /** Last computed loaded (sagging) terminal voltage (V). */
  voltage: number;
}

export function initBattery(cfg: BatteryConfig): BatteryState {
  return { remainingAh: cfg.capacityAh, voltage: cfg.maxVoltage };
}

/** Open-circuit voltage from SOC: linear taper from max down to ~3.3V/cell-ish. */
function restingVoltage(cfg: BatteryConfig, state: BatteryState): number {
  if (cfg.capacityAh <= 0) return cfg.maxVoltage;
  const soc = Math.max(0, Math.min(1, state.remainingAh / cfg.capacityAh));
  // Drop to 80% of max at empty - crude but monotonic and stable.
  return cfg.maxVoltage * (0.8 + 0.2 * soc);
}

/**
 * Advance the battery by dt given the current total thrust demand. Returns the
 * loaded terminal voltage and a thrust scale factor (loaded V / refV).
 */
export function updateBattery(
  cfg: BatteryConfig,
  state: BatteryState,
  totalThrust: number,
  dt: number,
): { state: BatteryState; voltage: number; voltageScale: number } {
  const ocv = restingVoltage(cfg, state);
  // Estimate current proportional to thrust (power ~ thrust at fixed efficiency).
  const thrustRatio = cfg.hoverThrust > 1e-6 ? totalThrust / cfg.hoverThrust : 0;
  const current = Math.max(0, cfg.hoverCurrent * thrustRatio);
  const loaded = Math.max(0, ocv - current * cfg.internalResistance);

  let remainingAh = state.remainingAh;
  if (cfg.capacityAh > 0) {
    remainingAh = Math.max(0, state.remainingAh - (current * dt) / 3600);
  }

  const refV = cfg.refVoltage > 1e-6 ? cfg.refVoltage : cfg.maxVoltage;
  return {
    state: { remainingAh, voltage: loaded },
    voltage: loaded,
    voltageScale: loaded / refV,
  };
}
