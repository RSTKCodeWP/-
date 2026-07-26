/**
 * @module AgentSchemas/Setup
 * @description zod schemas for the agent's setup / onboarding surfaces:
 * access URLs, setup steps, hardware checks, cloud-choice status, profile
 * suggestion, and the consolidated setup status response.
 *
 * @license GPL-3.0-only
 */

import { z } from "zod";

import { NullableNumber, NullableString, NumberLike } from "./primitives";

export const SetupAccessUrlSchema = z
  .object({
    kind: z.enum([
      "setup",
      "api",
      "mission_control",
      "video",
      "mavlink",
      "cloud",
    ]),
    label: z.string(),
    url: z.string(),
    source: z.enum([
      "local",
      "hotspot",
      "usb",
      "mdns",
      "cloud",
      "configured",
    ]),
    primary: z.boolean(),
  })
  .passthrough();

export const SetupStepSchema = z
  .object({
    id: z.string(),
    label: z.string(),
    state: z.enum([
      "complete",
      "needs_action",
      "optional",
      "blocked",
      "not_applicable",
    ]),
    detail: z.string(),
    action_label: z.string(),
    href: z.string(),
  })
  .passthrough();

export const CloudChoiceStatusSchema = z
  .object({
    mode: z.enum(["cloud", "self_hosted", "local"]),
    paired: z.boolean(),
    pair_code_required: z.boolean(),
    backend_url: z.string(),
    backend_reachable: z.boolean(),
    last_checked: NullableString,
  })
  .passthrough();

export const ProfileSuggestionSchema = z
  .object({
    detected: z.enum(["drone", "ground_station", "unconfigured"]),
    ground_role_hint: z.enum(["direct", "relay", "receiver"]),
    ground_score: NumberLike,
    air_score: NumberLike,
    mesh_capable: z.boolean(),
    signals: z.record(z.string(), z.boolean()),
    confirmed: z.boolean(),
    detected_at: NullableString,
  })
  .passthrough();

export const HardwareCheckItemSchema = z
  .object({
    id: z.string(),
    label: z.string(),
    required: z.boolean(),
    state: z.enum(["ok", "missing", "warning", "checking", "unknown"]),
    detail: z.string(),
    fix_hint: z.string(),
  })
  .passthrough();

export const HardwareCheckStatusSchema = z
  .object({
    profile: z.string(),
    ground_role: z.string(),
    items: z.array(HardwareCheckItemSchema),
    last_run: z.string(),
  })
  .passthrough();

export const SetupActionResultSchema = z
  .object({
    ok: z.boolean(),
    message: z.string(),
    data: z.record(z.string(), z.unknown()),
  })
  .passthrough();

export const SetupStatusSchema = z
  .object({
    version: z.string(),
    device_id: z.string(),
    device_name: z.string(),
    profile: z.string(),
    ground_role: z.string().optional(),
    setup_complete: z.boolean(),
    setup_finalized: z.boolean().optional(),
    completion_percent: NumberLike,
    next_action: z.string(),
    steps: z.array(SetupStepSchema),
    access_urls: z.array(SetupAccessUrlSchema),
    network: z
      .object({
        hostname: z.string(),
        mdns_host: z.string(),
        api_port: NumberLike,
        hotspot_enabled: z.boolean(),
        hotspot_ssid: z.string(),
        local_ips: z.array(z.string()),
      })
      .passthrough(),
    mavlink: z
      .object({
        connected: z.boolean(),
        port: NullableString,
        baud: NullableNumber,
        websocket_url: NullableString,
        public_websocket_url: NullableString,
      })
      .passthrough(),
    video: z
      .object({
        state: z.string(),
        whep_url: NullableString,
        public_whep_url: NullableString,
        recording: z.boolean(),
      })
      .passthrough(),
    remote_access: z
      .object({
        provider: z.enum(["none", "cloudflare"]),
        enabled: z.boolean(),
        configured: z.boolean(),
        status: z.enum([
          "disabled",
          "configured",
          "running",
          "stopped",
          "error",
        ]),
        public_urls: z.array(z.string()),
        error: z.string(),
      })
      .passthrough(),
    services: z.array(z.record(z.string(), z.unknown())),
    telemetry: z.record(z.string(), z.unknown()),
    cloud_choice: CloudChoiceStatusSchema.optional(),
    profile_suggestion: ProfileSuggestionSchema.optional(),
    hardware_check: z
      .union([HardwareCheckStatusSchema, z.null()])
      .optional(),
    skipped_steps: z.array(z.string()).optional(),
  })
  .passthrough();
