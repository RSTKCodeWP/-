/**
 * Vision-source message handlers.
 * Each function decodes a MAVLink payload and dispatches to subscriber callbacks.
 *
 * Optical flow values pass through unchanged. OPTICAL_FLOW_RAD's `temperature`
 * is converted from centi-degC (wire) to degC for consumers, matching the
 * SCALED_PRESSURE handler's convention.
 *
 * @module protocol/handlers/vision-handlers
 */

import type {
  OpticalFlowCallback, OpticalFlowRadCallback, OdometryCallback,
  VisionPositionEstimateCallback, VisionPositionDeltaCallback,
} from '../types';
import {
  decodeOpticalFlow, decodeOpticalFlowRad, decodeOdometry,
  decodeVisionPositionEstimate, decodeVisionPositionDelta,
} from '../mavlink-messages';

export function handleOpticalFlow(payload: DataView, callbacks: OpticalFlowCallback[]): void {
  const data = decodeOpticalFlow(payload);
  for (const cb of callbacks) {
    cb({
      timestamp: Date.now(),
      timeUsec: data.timeUsec,
      sensorId: data.sensorId,
      flowX: data.flowX,
      flowY: data.flowY,
      flowCompMX: data.flowCompMX,
      flowCompMY: data.flowCompMY,
      quality: data.quality,
      groundDistance: data.groundDistance,
      flowRateX: data.flowRateX,
      flowRateY: data.flowRateY,
    });
  }
}

export function handleOpticalFlowRad(payload: DataView, callbacks: OpticalFlowRadCallback[]): void {
  const data = decodeOpticalFlowRad(payload);
  for (const cb of callbacks) {
    cb({
      timestamp: Date.now(),
      timeUsec: data.timeUsec,
      sensorId: data.sensorId,
      integrationTimeUs: data.integrationTimeUs,
      integratedX: data.integratedX,
      integratedY: data.integratedY,
      integratedXgyro: data.integratedXgyro,
      integratedYgyro: data.integratedYgyro,
      integratedZgyro: data.integratedZgyro,
      temperature: data.temperature / 100, // cdegC → degC
      quality: data.quality,
      timeDeltaDistanceUs: data.timeDeltaDistanceUs,
      distance: data.distance,
    });
  }
}

export function handleOdometry(payload: DataView, callbacks: OdometryCallback[]): void {
  const data = decodeOdometry(payload);
  for (const cb of callbacks) {
    cb({
      timestamp: Date.now(),
      timeUsec: data.timeUsec,
      frameId: data.frameId,
      childFrameId: data.childFrameId,
      x: data.x, y: data.y, z: data.z,
      q: data.q,
      vx: data.vx, vy: data.vy, vz: data.vz,
      rollspeed: data.rollspeed,
      pitchspeed: data.pitchspeed,
      yawspeed: data.yawspeed,
      poseCovariance: data.poseCovariance,
      velocityCovariance: data.velocityCovariance,
      resetCounter: data.resetCounter,
      estimatorType: data.estimatorType,
      quality: data.quality,
    });
  }
}

export function handleVisionPositionEstimate(payload: DataView, callbacks: VisionPositionEstimateCallback[]): void {
  const data = decodeVisionPositionEstimate(payload);
  for (const cb of callbacks) {
    cb({
      timestamp: Date.now(),
      usec: data.usec,
      x: data.x, y: data.y, z: data.z,
      roll: data.roll,
      pitch: data.pitch,
      yaw: data.yaw,
      covariance: data.covariance,
      resetCounter: data.resetCounter,
    });
  }
}

export function handleVisionPositionDelta(payload: DataView, callbacks: VisionPositionDeltaCallback[]): void {
  const data = decodeVisionPositionDelta(payload);
  for (const cb of callbacks) {
    cb({
      timestamp: Date.now(),
      timeUsec: data.timeUsec,
      timeDeltaUsec: data.timeDeltaUsec,
      angleDelta: data.angleDelta,
      positionDelta: data.positionDelta,
      confidence: data.confidence,
    });
  }
}
