/**
 * MSP payload encoders for power and motor output: motor config, battery
 * config, and raw per-motor commands.
 *
 * @module protocol/msp/encoders/power
 */

import { makeBuffer, push8, push16 } from "./helpers";

/**
 * MSP_SET_MOTOR_CONFIG (222)
 *   U16 minThrottle
 *   U16 maxThrottle
 *   U16 minCommand
 *   U8  motorPoles
 *   U8  useDshotTelemetry
 */
export function encodeMspSetMotorConfig(config: {
  minThrottle: number;
  maxThrottle: number;
  minCommand: number;
  motorPoles: number;
  useDshotTelemetry: boolean;
}): Uint8Array {
  const { buf, dv } = makeBuffer(8);
  push16(dv, 0, config.minThrottle);
  push16(dv, 2, config.maxThrottle);
  push16(dv, 4, config.minCommand);
  push8(dv, 6, config.motorPoles);
  push8(dv, 7, config.useDshotTelemetry ? 1 : 0);
  return buf;
}


/**
 * MSP_SET_BATTERY_CONFIG (33)
 *   U8  vbatMinCell (×10, legacy)
 *   U8  vbatMaxCell (×10, legacy)
 *   U8  vbatWarningCell (×10, legacy)
 *   U16 capacity
 *   U8  voltageMeterSource
 *   U8  currentMeterSource
 *   U16 vbatMinCell (×100)
 *   U16 vbatMaxCell (×100)
 *   U16 vbatWarningCell (×100)
 */
export function encodeMspSetBatteryConfig(config: {
  vbatMinCellVoltage: number;
  vbatMaxCellVoltage: number;
  vbatWarningCellVoltage: number;
  capacity: number;
  voltageMeterSource: number;
  currentMeterSource: number;
}): Uint8Array {
  const { buf, dv } = makeBuffer(13);
  push8(dv, 0, Math.round(config.vbatMinCellVoltage * 10));
  push8(dv, 1, Math.round(config.vbatMaxCellVoltage * 10));
  push8(dv, 2, Math.round(config.vbatWarningCellVoltage * 10));
  push16(dv, 3, config.capacity);
  push8(dv, 5, config.voltageMeterSource);
  push8(dv, 6, config.currentMeterSource);
  push16(dv, 7, Math.round(config.vbatMinCellVoltage * 100));
  push16(dv, 9, Math.round(config.vbatMaxCellVoltage * 100));
  push16(dv, 11, Math.round(config.vbatWarningCellVoltage * 100));
  return buf;
}


/**
 * MSP_SET_MOTOR (214)
 * U16 per motor
 */
export function encodeMspSetMotor(motors: number[]): Uint8Array {
  const { buf, dv } = makeBuffer(motors.length * 2);
  for (let i = 0; i < motors.length; i++) {
    push16(dv, i * 2, motors[i]);
  }
  return buf;
}

