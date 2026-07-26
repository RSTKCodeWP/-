/**
 * Shared types for motor test IPC + telemetry
 */

export type MotorTestThrottleType = 'percent' | 'pwm';

export interface MotorTestStartRequest {
  /** 1-based motor index */
  motor: number;
  /** Throttle value (0-100 for percent, 1000-2000 for pwm) */
  throttle: number;
  /** Duration in seconds */
  duration: number;
  /** Throttle interpretation */
  throttleType: MotorTestThrottleType;
  /**
   * Number of motors to sequence through.
   * 0 = test only `motor` (default).
   * N > 0 = start at `motor` and sequence through N motors in TestOrder.
   */
  motorCount?: number;
}

export interface MotorTestResponse {
  success: boolean;
  error?: string;
}

export interface VibrationData {
  /** X-axis vibration (m/s²) */
  x: number;
  /** Y-axis vibration (m/s²) */
  y: number;
  /** Z-axis vibration (m/s²) */
  z: number;
  /** Accel 1 clipping count */
  clip0: number;
  /** Accel 2 clipping count */
  clip1: number;
  /** Accel 3 clipping count */
  clip2: number;
  /** Timestamp (ms) */
  timestamp: number;
}

export interface EscMotorTelemetry {
  /** RPM */
  rpm: number;
  /** Temperature (°C) */
  tempC: number;
  /** Voltage (V) */
  voltageV: number;
  /** Current (A) */
  currentA: number;
}

export interface EscTelemetryData {
  /**
   * Indexed 0-based: motors[0] = motor 1.
   * Sparse — undefined entries mean that motor is not reporting telemetry.
   */
  motors: Array<EscMotorTelemetry | undefined>;
  /** Timestamp (ms) */
  timestamp: number;
}

/**
 * Raw PWM values that the FC is sending to its servo/motor outputs.
 * Indexed 0-based: outputs[0] = servo output 1.
 * Universally available regardless of ESC capability — works on plain PWM
 * ESCs with no telemetry. Range typically 1000-2000 µs.
 */
export interface ServoOutputData {
  outputs: number[];
  /** Timestamp (ms) */
  timestamp: number;
}

/** Frame layout entry from ap-motor-layouts.json */
export interface FrameLayoutMotor {
  Number: number;
  TestOrder: number;
  Rotation: 'CW' | 'CCW' | '?';
  Roll: number;
  Pitch: number;
}

export interface FrameLayout {
  Class: number;
  ClassName: string;
  Type: number;
  TypeName: string;
  motors: FrameLayoutMotor[];
}

export interface FrameLayoutsFile {
  Version: string;
  layouts: FrameLayout[];
}
