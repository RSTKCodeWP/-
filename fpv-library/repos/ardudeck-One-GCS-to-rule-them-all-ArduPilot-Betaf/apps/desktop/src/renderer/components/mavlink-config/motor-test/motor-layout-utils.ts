/**
 * Motor layout lookup and geometry helpers.
 *
 * Layout data is bundled from MissionPlanner-ref/APMotorLayout.json into
 * src/shared/ap-motor-layouts.json. The JSON contains entries keyed by
 * (FRAME_CLASS, FRAME_TYPE) with Roll/Pitch positions that we normalize
 * into SVG coordinates for the frame diagram.
 */

import layoutsJson from '../../../../shared/ap-motor-layouts.json';
import type { FrameLayout, FrameLayoutMotor, FrameLayoutsFile } from '../../../../shared/motor-test-types';

const layoutsFile = layoutsJson as FrameLayoutsFile;

/**
 * Find the frame layout matching the given FRAME_CLASS and FRAME_TYPE.
 * Returns null if no exact match is found.
 */
export function findFrameLayout(frameClass: number, frameType: number): FrameLayout | null {
  for (const layout of layoutsFile.layouts) {
    if (layout.Class === frameClass && layout.Type === frameType) {
      return layout;
    }
  }
  return null;
}

/**
 * Fallback: build a generic circular layout with N motors evenly spaced.
 * Used when FRAME_CLASS/TYPE can't be resolved.
 */
export function buildGenericLayout(motorCount: number): FrameLayout {
  const motors: FrameLayoutMotor[] = [];
  for (let i = 0; i < motorCount; i++) {
    const angle = (i / motorCount) * Math.PI * 2 - Math.PI / 2;
    motors.push({
      Number: i + 1,
      TestOrder: i + 1,
      Rotation: i % 2 === 0 ? 'CW' : 'CCW',
      // Roll is X, Pitch is Y. Unit circle.
      Roll: Math.cos(angle) * 0.5,
      Pitch: Math.sin(angle) * 0.5,
    });
  }
  return {
    Class: 0,
    ClassName: 'Generic',
    Type: 0,
    TypeName: `${motorCount}-motor generic`,
    motors,
  };
}

export interface MotorPosition {
  number: number;
  testOrder: number;
  rotation: 'CW' | 'CCW' | '?';
  /** SVG X coordinate in the [0, size] range */
  cx: number;
  /** SVG Y coordinate in the [0, size] range */
  cy: number;
}

/**
 * Convert a layout's Roll/Pitch positions to SVG coordinates centered in a
 * square canvas of the given size.
 *
 * Roll axis: +X (right). Pitch axis: +Y (forward) — but SVG Y is inverted.
 * We pad so motors are drawn well inside the canvas edges.
 */
export function layoutToSvgPositions(layout: FrameLayout, size: number, pad = 40): MotorPosition[] {
  if (layout.motors.length === 0) return [];

  // Find the max absolute Roll/Pitch to normalize to [-1, 1]
  let maxExtent = 0;
  for (const m of layout.motors) {
    maxExtent = Math.max(maxExtent, Math.abs(m.Roll), Math.abs(m.Pitch));
  }
  if (maxExtent === 0) maxExtent = 1;

  const radius = (size - pad * 2) / 2;
  const center = size / 2;

  return layout.motors.map((m) => ({
    number: m.Number,
    testOrder: m.TestOrder,
    rotation: m.Rotation,
    // Roll → X. Roll is a torque factor: -Roll = right side of vehicle = +X in SVG.
    cx: center - (m.Roll / maxExtent) * radius,
    // Pitch → Y. +Pitch = forward = top of SVG = -Y, so we subtract.
    cy: center - (m.Pitch / maxExtent) * radius,
  }));
}

/**
 * Convert TestOrder number (1-based) to a letter label like "A", "B", etc.
 */
export function testOrderToLabel(testOrder: number): string {
  return String.fromCharCode('A'.charCodeAt(0) + testOrder - 1);
}

/**
 * Read FRAME_CLASS / FRAME_TYPE from a parameter map, checking both the
 * plain ArduPilot names and the Q_ prefixed QuadPlane versions.
 * Returns null if either value is missing.
 */
export function getFrameClassType(
  params: Map<string, number> | Record<string, number> | ((key: string) => number | undefined)
): { frameClass: number; frameType: number } | null {
  const get = (key: string): number | undefined => {
    if (typeof params === 'function') return params(key);
    if (params instanceof Map) return params.get(key);
    return params[key];
  };

  let frameClass = get('FRAME_CLASS');
  let frameType = get('FRAME_TYPE');

  if (frameClass === undefined || frameType === undefined) {
    frameClass = get('Q_FRAME_CLASS');
    frameType = get('Q_FRAME_TYPE');
  }

  if (frameClass === undefined || frameType === undefined) return null;
  return { frameClass, frameType };
}
