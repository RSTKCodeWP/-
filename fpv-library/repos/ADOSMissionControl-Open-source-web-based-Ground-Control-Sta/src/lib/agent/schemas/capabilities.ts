/**
 * @module AgentSchemas/Capabilities
 * @description zod schemas for the agent capabilities payload: camera,
 * compute, vision, models, features (legacy + array shapes),
 * and the consolidated raw block used by `/api/status/full` and
 * `/api/capabilities`.
 *
 * @license GPL-3.0-only
 */

import { z } from "zod";

import { NullableNumber, NullableString, NumberLike } from "./primitives";
import { NavigationCapabilitySchema } from "./navigation";

const CameraCapabilitySchema = z
  .object({
    name: z.string().optional(),
    type: z.string().optional(),
    device: z.string().optional(),
    resolution: z.string().optional(),
    fps: NumberLike.optional(),
    streaming: z.boolean().optional(),
  })
  .passthrough();

// A host-resolved video leg the status/heartbeat producer folded in (id + a
// dialable whepUrl); role/codec are advisory labels.
const VideoStreamLegSchema = z
  .object({
    id: z.string(),
    role: z.string().optional(),
    codec: z.string().optional(),
    whepUrl: z.string(),
  })
  .passthrough();

const ComputeCapabilitySchema = z
  .object({
    npu_available: z.boolean().optional(),
    npu_runtime: z
      .union([z.enum(["rknn", "tensorrt", "tflite", "opencv_dnn"]), z.null()])
      .optional(),
    npu_tops: NumberLike.optional(),
    npu_utilization_pct: NumberLike.optional(),
    gpu_available: z.boolean().optional(),
  })
  .passthrough();

const VisionStateSchema = z
  .object({
    engine_state: z
      .enum(["off", "initializing", "ready", "active", "degraded", "error"])
      .optional(),
    active_behavior: NullableString.optional(),
    behavior_state: z
      .union([
        z.enum([
          "idle",
          "designating",
          "searching",
          "tracking",
          "executing",
          "paused",
        ]),
        z.null(),
      ])
      .optional(),
    fps: NumberLike.optional(),
    inference_ms: NumberLike.optional(),
    model_loaded: NullableString.optional(),
    track_count: NumberLike.optional(),
    target_locked: z.boolean().optional(),
    target_confidence: NumberLike.optional(),
    obstacle_mode: z.enum(["off", "brake", "detour"]).optional(),
    nearest_obstacle_m: NullableNumber.optional(),
    threat_level: z.enum(["green", "yellow", "red"]).optional(),
    enabled: z.boolean().optional(),
    error_message: z.string().optional(),
  })
  .passthrough();

const ModelCacheInfoSchema = z
  .object({
    installed: z.array(z.unknown()).optional(),
    cache_used_mb: NumberLike.optional(),
    cache_max_mb: NumberLike.optional(),
    registry_url: z.string().optional(),
  })
  .passthrough();

export const AgentCapabilitiesRawSchema = z
  .object({
    tier: NumberLike.optional(),
    cameras: z.array(CameraCapabilitySchema).optional(),
    videoStreams: z.array(VideoStreamLegSchema).optional(),
    compute: ComputeCapabilitySchema.optional(),
    vision: VisionStateSchema.optional(),
    models: z
      .union([z.array(z.unknown()), ModelCacheInfoSchema])
      .optional(),
    navigation: NavigationCapabilitySchema.optional(),
  })
  .passthrough();

export type AgentCapabilitiesRaw = z.infer<typeof AgentCapabilitiesRawSchema>;
