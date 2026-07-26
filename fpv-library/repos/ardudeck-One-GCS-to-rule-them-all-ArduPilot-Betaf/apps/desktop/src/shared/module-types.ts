/**
 * Module Manager shared types
 * Used by main process (module-manager, IPC) and renderer (store, view)
 */

/** A module installed on this device */
export interface InstalledModule {
  slug: string;
  name: string;
  version: string;
  installedAt: string; // ISO 8601
  licenseKey: string;
  licenseType: 'perpetual' | 'subscription' | 'trial';
  bundleName: string | null; // null if single-module license
  installPath?: string; // filesystem path where bundle was extracted (installable only)
  manifestVersion?: number; // schema version from module.json
  activatable?: boolean; // built-in feature enabled by license, no bundle downloaded
  /** User toggle: false = keep installed but don't load. Absent means enabled. */
  enabled?: boolean;
}

/** License key payload (decoded from key, verified with Ed25519) */
export interface LicensePayload {
  product: string;
  email: string;
  type: 'perpetual' | 'subscription' | 'trial';
  maxDevices: number;
  expiresAt?: string;
  maxVersion?: string;
  issuedAt: string;
}

/** Progress event pushed from main to renderer during activation */
export interface ModuleProgress {
  stage: 'validating' | 'activating' | 'downloading' | 'verifying' | 'complete' | 'error';
  message: string;
  percent?: number;
}

/** API response types (mirror Hangar API) */
export interface ActivateResponse {
  ok: boolean;
  modules: string[];
  bundle: string | null;
  // Subset of `modules` whose code already ships in the app - enable in place
  // instead of downloading a bundle.
  activatable?: string[];
  error?: string;
}

export interface HeartbeatResponse {
  valid: boolean;
  revoked?: boolean;
}

export interface UpdateAvailable {
  slug: string;
  name: string;
  currentVersion: string;
  latestVersion: string;
  changelog: string | null;
  bundleSize: number;
}

export interface CheckUpdatesResponse {
  updates: UpdateAvailable[];
}
