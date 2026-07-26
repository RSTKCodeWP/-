import type { LucideIcon } from 'lucide-react';
import type { VehicleProfile, VehicleType } from '../../stores/settings-store.js';

/**
 * One parameter the template wants to set. `reason` is shown in the compare
 * modal so the user understands why each value was picked (tied to a profile
 * field when possible, e.g. "cells × 3.5 = 14.0V low-voltage threshold").
 */
export interface ParamSpec {
  name: string;
  value: number;
  reason: string;
  requiresReboot?: boolean;  // informational override; metadata is still checked
}

/**
 * A vehicle template = one self-contained configuration of an ArduPilot airframe.
 *
 * - `defaults` seeds a fresh profile when the user picks this template.
 * - `toParams` emits ArduPilot core params (FRAME_CLASS, BATT_*, AIRSPEED_*, Q_*).
 * - `toSimParams` emits SIM_* params (SITL fidelity — batt curves, engine mul,
 *   servo speed, drag). Empty array for non-SITL-relevant templates.
 * - `inferFrom` returns a 0..1 confidence that the given param cache looks like
 *   a vehicle running *this* template — used for reverse import.
 */
export interface VehicleTemplate {
  slug: string;
  name: string;
  description: string;
  icon: LucideIcon;
  vehicleType: VehicleType;
  category: 'multirotor' | 'fixed-wing' | 'vtol' | 'rover' | 'boat' | 'sub';
  defaults: Partial<VehicleProfile>;

  toParams: (p: VehicleProfile) => ParamSpec[];
  toSimParams: (p: VehicleProfile) => ParamSpec[];
  inferFrom: (paramMap: Map<string, number>) => number;
}

/**
 * Snapshot taken before an apply, used for undo/rollback.
 * Stored in the profile-snapshots store (electron-store backed).
 */
export interface ProfileSnapshot {
  id: string;
  profileId: string;
  templateSlug: string;
  createdAt: string;               // ISO
  target: { isSitl: boolean; sysid: number; label: string };
  before: Record<string, number>;  // values as they were before apply
  applied: Record<string, number>; // values that were written
  reason: string;                  // e.g. "Apply Tailsitter Delta Duo"
}

/**
 * Result of computing a diff for a profile+template against a live param cache.
 */
export interface ProfileDiffResult {
  /** Params that exist in the cache and differ from target → safe to apply */
  changes: Array<{
    name: string;
    currentValue: number;
    targetValue: number;
    type: number;        // MAV_PARAM_TYPE from the live cache
    reason: string;
    requiresReboot: boolean;
  }>;
  /** Params the template wants to set but aren't in the cache (firmware doesn't expose them on this build) */
  unknownParams: Array<{ name: string; targetValue: number; reason: string }>;
  /** Params that already match the target value → nothing to do */
  unchangedParams: Array<{ name: string; value: number }>;
}
