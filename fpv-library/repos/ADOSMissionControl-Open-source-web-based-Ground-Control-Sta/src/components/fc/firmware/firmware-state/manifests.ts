/**
 * @module fc/firmware/firmware-state/manifests
 * @description Shared firmware-manifest client singletons. One instance
 * each, reused by the per-stack hooks so the in-memory + IndexedDB
 * caches are shared across the picker's lifetime.
 * @license GPL-3.0-only
 */

import { ArduPilotManifest } from "@/lib/protocol/firmware/manifest";
import { BetaflightManifest } from "@/lib/protocol/firmware/betaflight-manifest";
import { PX4Manifest } from "@/lib/protocol/firmware/px4-manifest";
import { AdosAgentManifest } from "@/lib/protocol/firmware/ados-agent-manifest";

export const apManifest = new ArduPilotManifest();
export const bfManifest = new BetaflightManifest();
export const px4Manifest = new PX4Manifest();
export const adosManifest = new AdosAgentManifest();
