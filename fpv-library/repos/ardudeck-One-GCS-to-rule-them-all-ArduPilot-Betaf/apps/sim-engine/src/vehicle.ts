/**
 * A single simulated vehicle. Holds physics params, fidelity state (battery,
 * wind gust, RNG), and current state, and advances the dynamics with internal
 * sub-stepping for stability when SITL requests a large frame interval.
 *
 * Supports copter / plane / rover. Battery sag and ground effect apply to
 * copters; wind and sensor noise apply to all kinds.
 */

import {
  initBattery,
  initialPlaneState,
  initialRoverState,
  initialState,
  initWind,
  makeRng,
  stepCopter,
  stepPlane,
  stepRover,
  updateBattery,
  updateWind,
  applySensorNoise,
  motorThrusts,
  multirotorParamsFromFrame,
  CALM_WIND,
  NO_SENSOR_NOISE,
  DEFAULT_ENVIRONMENT,
  type BatteryConfig,
  type BatteryState,
  type Environment,
  type MultirotorParams,
  type PlaneParams,
  type RoverParams,
  type Rng,
  type SensorNoiseConfig,
  type VehicleState,
  type WindConfig,
  type WindState,
  type FrameLike,
} from '@ardudeck/sim-physics';

const MAX_SUBSTEP = 0.0025;

export type VehicleKind = 'copter' | 'plane' | 'rover';

export interface HomeLocation {
  lat: number;
  lng: number;
  alt: number;
  heading: number;
}

export interface FidelityConfig {
  wind: WindConfig;
  noise: SensorNoiseConfig;
  battery?: BatteryConfig;
  groundEffect: boolean;
}

export const DEFAULT_FIDELITY: FidelityConfig = {
  wind: CALM_WIND,
  noise: NO_SENSOR_NOISE,
  groundEffect: true,
};

export const DEFAULT_PLANE_PARAMS: PlaneParams = {
  mass: 2.0, wingArea: 0.4, span: 1.5, chord: 0.27,
  cl0: 0.2, clAlpha: 5.0, cd0: 0.03, inducedK: 0.05, maxThrust: 12,
  elevatorEffect: 1.2, aileronEffect: 1.0, rudderEffect: 0.8,
  pitchDamp: 2.0, rollDamp: 1.5, yawDamp: 2.0,
};

export const DEFAULT_ROVER_PARAMS: RoverParams = {
  mass: 5, maxThrust: 40, dragCoef: 4, wheelbase: 0.3, maxSteer: 0.6,
};

/** Build a battery config from a multicopter frame (for sag simulation). */
export function batteryFromFrame(frame: FrameLike & {
  maxVoltage: number; refVoltage: number; battCapacityAh: number; refBatRes: number; refCurrent: number;
}, hoverThrust: number): BatteryConfig {
  return {
    maxVoltage: frame.maxVoltage,
    refVoltage: frame.refVoltage,
    capacityAh: frame.battCapacityAh,
    internalResistance: frame.refBatRes,
    hoverCurrent: frame.refCurrent,
    hoverThrust,
  };
}

export class SimVehicle {
  state: VehicleState;
  private windState: WindState = initWind();
  private batteryState: BatteryState | null;
  private rng: Rng;

  constructor(
    public readonly id: string,
    public readonly kind: VehicleKind,
    public readonly params: MultirotorParams | PlaneParams | RoverParams,
    public readonly env: Environment,
    public home: HomeLocation,
    public readonly fidelity: FidelityConfig = DEFAULT_FIDELITY,
    seed = 1,
  ) {
    this.state = this.makeInitial();
    this.batteryState = fidelity.battery ? initBattery(fidelity.battery) : null;
    this.rng = makeRng(seed);
  }

  private makeInitial(): VehicleState {
    if (this.kind === 'plane') return initialPlaneState();
    if (this.kind === 'rover') return initialRoverState();
    return initialState();
  }

  /** Current loaded battery voltage, or null if no battery model. */
  get batteryVoltage(): number | null {
    return this.batteryState ? this.batteryState.voltage : null;
  }

  reset(): void {
    this.state = this.makeInitial();
    this.windState = initWind();
    this.batteryState = this.fidelity.battery ? initBattery(this.fidelity.battery) : null;
  }

  step(pwm: number[], dt: number): VehicleState {
    const clamped = Math.max(1e-4, Math.min(0.05, dt));
    const substeps = Math.max(1, Math.ceil(clamped / MAX_SUBSTEP));
    const sub = clamped / substeps;

    // Evolve wind once for the whole frame.
    const windResult = updateWind(this.fidelity.wind, this.windState, clamped, this.rng);
    this.windState = windResult.state;
    const env: Environment = { ...this.env, wind: windResult.wind };

    for (let i = 0; i < substeps; i++) {
      this.state = this.integrate(pwm, env, sub);
    }

    return applySensorNoise(this.state, this.fidelity.noise, this.rng);
  }

  private integrate(pwm: number[], env: Environment, dt: number): VehicleState {
    if (this.kind === 'plane') {
      return stepPlane(pwm, this.state, this.params as PlaneParams, env, dt).state;
    }
    if (this.kind === 'rover') {
      return stepRover(pwm, this.state, this.params as RoverParams, env, dt).state;
    }

    const mp = this.params as MultirotorParams;
    let voltageScale = 1;
    if (this.batteryState && this.fidelity.battery) {
      const thrusts = motorThrusts(pwm, mp, env.gravity, 1);
      const total = thrusts.reduce((a, b) => a + b, 0);
      const r = updateBattery(this.fidelity.battery, this.batteryState, total, dt);
      this.batteryState = r.state;
      voltageScale = r.voltageScale;
    }
    return stepCopter(pwm, this.state, mp, env, dt, {
      voltageScale,
      groundEffect: this.fidelity.groundEffect,
    }).state;
  }
}

export { multirotorParamsFromFrame };
