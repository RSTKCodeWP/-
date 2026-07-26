/**
 * Web Worker for PID analysis.
 *
 * Runs the full analysis pipeline off the main thread:
 *   parse log → extract data → FFT → step response → tracking → motors → score
 *
 * IMPORTANT: Web workers cannot use @/ path aliases. All imports are relative.
 *
 * @license GPL-3.0-only
 */

import { parseDataFlashLog } from "../dataflash-parser";
import { extractLogData, extractVibration } from "./log-extractor";
import { computeFFT } from "./fft";
import { extractStepResponses } from "./step-response";
import { analyzeTracking } from "./tracking-quality";
import { analyzeMotors } from "./motor-analysis";
import { scoreFFTQuality, scoreStepResponse, detectIssues } from "./pid-scoring";
import type {
  WorkerInMessage,
  WorkerOutMessage,
  PidAnalysisResult,
  FFTResult,
  StepResponseResult,
  TrackingQualityResult,
} from "./types";

// ---------------------------------------------------------------------------
// Progress helper
// ---------------------------------------------------------------------------

function postProgress(stage: string, percent: number): void {
  const msg: WorkerOutMessage = { type: "progress", stage, percent };
  self.postMessage(msg);
}

function postResult(data: PidAnalysisResult): void {
  const msg: WorkerOutMessage = { type: "result", data };
  self.postMessage(msg);
}

function postError(message: string): void {
  const msg: WorkerOutMessage = { type: "error", message };
  self.postMessage(msg);
}

// ---------------------------------------------------------------------------
// Worker message handler
// ---------------------------------------------------------------------------

self.onmessage = (event: MessageEvent<WorkerInMessage>) => {
  const msg = event.data;

  if (msg.type === "cancel") {
    return;
  }

  if (msg.type === "analyze") {
    try {
      // 1. Parse log
      postProgress("Parsing log file...", 10);
      const log = parseDataFlashLog(msg.buffer);

      // 2. Extract data
      postProgress("Extracting data...", 20);
      const data = extractLogData(log, msg.buffer.byteLength);

      // 3. FFT on each gyro axis
      postProgress("Computing FFT...", 40);
      const fft: FFTResult = {
        roll: computeFFT(data.gyro.roll, data.sampleRates.gyro || 400, "roll"),
        pitch: computeFFT(data.gyro.pitch, data.sampleRates.gyro || 400, "pitch"),
        yaw: computeFFT(data.gyro.yaw, data.sampleRates.gyro || 400, "yaw"),
      };

      // 4. Step response
      postProgress("Analyzing step response...", 55);
      const stepResponse: StepResponseResult = {
        roll: extractStepResponses(data.desiredRate.roll, data.actualRate.roll, "roll"),
        pitch: extractStepResponses(data.desiredRate.pitch, data.actualRate.pitch, "pitch"),
        yaw: extractStepResponses(data.desiredRate.yaw, data.actualRate.yaw, "yaw"),
      };

      // 5. Tracking quality
      postProgress("Evaluating tracking...", 70);
      const rollTracking = analyzeTracking(data.desiredRate.roll, data.actualRate.roll, "roll");
      const pitchTracking = analyzeTracking(data.desiredRate.pitch, data.actualRate.pitch, "pitch");
      const yawTracking = analyzeTracking(data.desiredRate.yaw, data.actualRate.yaw, "yaw");
      const tracking: TrackingQualityResult = {
        roll: rollTracking,
        pitch: pitchTracking,
        yaw: yawTracking,
        overallScore: Math.round(
          (rollTracking.score + pitchTracking.score + yawTracking.score) / 3,
        ),
      };

      // 6. Motor analysis
      postProgress("Analyzing motors...", 85);
      const motors = analyzeMotors(data.motors);

      // 7. Compute overall tune score and identify issues
      postProgress("Scoring...", 95);

      const vibration = extractVibration(log);

      // Weighted score: tracking 40%, motor health 25%, FFT quality 20%, step response 15%
      const fftScore = scoreFFTQuality(fft);
      const stepScore = scoreStepResponse(stepResponse);

      const tuneScore = Math.round(
        tracking.overallScore * 0.4 +
          motors.healthScore * 0.25 +
          fftScore * 0.2 +
          stepScore * 0.15,
      );

      const issues = detectIssues(fft, stepResponse, tracking, motors, vibration.level);

      const result: PidAnalysisResult = {
        metadata: data.metadata,
        fft,
        stepResponse,
        tracking,
        motors,
        vibration,
        tuneScore,
        issues,
      };

      postResult(result);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Unknown analysis error";
      postError(message);
    }
  }
};
