/**
 * Shared types for the ArduDeck FC-side script installer.
 *
 * ArduDeck installs Lua scripts onto the flight controller's SD card to add
 * commands the autopilot doesn't natively support (e.g. Orbit when MODE_CIRCLE
 * is disabled in the build). This module defines the public contracts shared
 * between the main-process installer service and the renderer install UI.
 *
 * Design principles:
 *  - Never auto-install. Every install requires explicit consent.
 *  - Every parameter change and FTP write is recorded in the audit log.
 *  - State is per-FC (keyed by autopilot UID), so trust decisions don't leak
 *    between vehicles.
 *  - The renderer subscribes to InstallState updates - the main process owns
 *    the truth and pushes changes.
 */

/**
 * MAVLink command IDs reserved for user / scripted commands.
 * ArduPilot Lua scripts can register handlers for MAV_CMD_USER_1..5.
 *
 * The ArduDeck script funnels everything through MAV_CMD_USER_1 and uses
 * COMMAND_INT param4 as a sub-command discriminator (see SUB_CMD below).
 * That gives us unlimited commands without burning more MAV_CMD slots.
 */
export const USER_CMD = {
  AD: 31010,        // MAV_CMD_USER_1 - ArduDeck dispatcher
  ORBIT: 31010,     // legacy alias - everything still maps to USER_1
} as const;

/**
 * Sub-command IDs sent in COMMAND_INT param4. Must stay in sync with
 * SUB_CMD_* constants in src/main/lua-scripts/ardudeck_commands.lua.
 */
export const SUB_CMD = {
  ORBIT:      0,
  SPIRAL:     1,
  // 2 was POI - removed (useless without live RC-stick passthrough). Slot
  // intentionally reserved so future commands don't shift the others.
  WATCHTOWER: 3,
  CLIMB_RTL:  4,
  /** Cinematography pair — both lock yaw to a clicked target via
   *  vehicle:set_target_pos_NED(use_yaw=true) and walk position per tick. */
  REVEAL:     5,
  STRAFE:     6,
  /** Fly to the clicked point at current altitude in GUIDED, then switch to
   *  LAND. Replaces the native NAV_LAND path which (in ArduCopter) ignores
   *  the lat/lon and just descends in place. */
  LAND_AT:    7,
  /** Tell the script to deactivate its current command without starting a new
   *  one. Used by the GCS dispatcher to release the vehicle before issuing a
   *  native command (Move / Land / DO_REPOSITION) — without this the script's
   *  per-tick set_target_location keeps overriding the new native target. */
  STOP:       255,
} as const;

export type UserCommandName = keyof typeof USER_CMD;
export type SubCommandName = keyof typeof SUB_CMD;

/**
 * Static manifest describing a single command implemented by the script.
 * Used by the preview UI to explain what each command does.
 */
export interface CommandModule {
  /** Sub-command name (orbit, spiral, ...) — display + identification. */
  name: SubCommandName;
  /** Human-readable label shown in UI. */
  label: string;
  /** One-paragraph description of what the script does on the FC. */
  description: string;
  /** MAV_CMD id - always USER_1 (31010) for the unified dispatcher. */
  trigger: number;
  /** Sub-command id sent in param4 of the COMMAND_INT. */
  subId: number;
  /** Brief description of params (param1..4, x, y, z) the command takes. */
  paramSchema: string;
}

/**
 * Manifest of the script bundle ArduDeck ships in this app version.
 * Computed at build time from the Lua source file.
 */
export interface ScriptManifest {
  /** Filename written to /APM/scripts/ on the FC. */
  filename: string;
  /** Semver-style version string. Bumped per Lua source change. */
  version: string;
  /** SHA256 of the Lua source bytes - lets the user verify what they're installing. */
  sha256: string;
  /** Size of the script in bytes (informational). */
  sizeBytes: number;
  /** Required FC parameters and minimum values. */
  requirements: ScriptRequirement[];
  /** Commands the script provides. */
  commands: CommandModule[];
  /** Named-value heartbeat the script publishes. */
  heartbeat: { name: string; intervalSec: number };
}

export interface ScriptRequirement {
  param: string;
  /** Human description, e.g. "Lua scripting must be enabled". */
  why: string;
  /** Required value if exact, OR minimum value. */
  exact?: number;
  min?: number;
  /** Whether failing this requirement requires a reboot to fix. */
  rebootIfChanged: boolean;
}

/**
 * Result of a single preflight check run against the connected FC.
 * Severity controls UI behavior:
 *   pass  - green checkmark, no action needed
 *   warn  - yellow, install proceeds (e.g. vehicle armed)
 *   block - red, install button disabled until resolved
 */
export type PreflightSeverity = 'pass' | 'warn' | 'block';

export interface PreflightCheck {
  id: string;
  /** Short label for UI row, e.g. "SCR_ENABLE = 1". */
  label: string;
  severity: PreflightSeverity;
  /** Detail text shown when expanded. */
  detail: string;
  /** If non-null, an inline-fix action the renderer can dispatch. */
  fix: PreflightFix | null;
  /**
   * Current value (for params) or current state (e.g. "true" for armed).
   * Optional for non-numeric checks.
   */
  currentValue?: number | string;
  expectedValue?: number | string;
}

/**
 * An action that can resolve a failed preflight check. The renderer requests
 * it via IPC and the main process orchestrates (param set + optional reboot).
 */
export type PreflightFix =
  | { type: 'set_param'; param: string; value: number; requiresReboot: boolean }
  | { type: 'disarm' }
  | { type: 'reboot' };

/**
 * Per-FC registry entry. Persisted to disk via electron-store, keyed by
 * autopilot UID (the unique ID from AUTOPILOT_VERSION). Never sent over the
 * network - this is local state only.
 */
export interface FcRegistryEntry {
  autopilotUid: string;
  /** Human label for the FC (vehicle name, model, etc). Best-effort. */
  vehicleLabel: string | null;
  installedAt: string; // ISO 8601
  scriptVersion: string;
  scriptSha256: string;
  enabledCommands: SubCommandName[];
  paramChanges: ParamChange[];
  auditLog: AuditEntry[];
  /**
   * How the script got onto the FC:
   *   'ftp'    - ArduDeck wrote it via MAVLink-FTP
   *   'manual' - User side-loaded the file (we picked it up via heartbeat)
   *   'unknown' - Pre-existing entry from before this field was tracked
   */
  installMethod?: 'ftp' | 'manual' | 'unknown';
}

export interface ParamChange {
  param: string;
  before: number;
  after: number;
  /** ISO timestamp of when ArduDeck made this change. */
  timestamp: string;
  /** Whether the original value can be restored on uninstall. */
  revertible: boolean;
}

export type AuditEventType =
  | 'install'
  | 'update'
  | 'uninstall'
  | 'param_set'
  | 'reboot'
  | 'ftp_write'
  | 'ftp_delete'
  | 'consent_granted'
  | 'consent_denied'
  | 'install_failed';

export interface AuditEntry {
  type: AuditEventType;
  timestamp: string;
  /** Human-readable summary. */
  summary: string;
  /** Optional structured payload for forensics. */
  data?: Record<string, unknown>;
}

/**
 * Discriminated union representing every state the install flow can be in.
 * The renderer pattern-matches on `phase` to render the right UI. Each phase
 * carries only the data it needs.
 */
export type InstallPhase =
  | { phase: 'idle' }
  | { phase: 'preflight'; checks: PreflightCheck[] }
  | { phase: 'awaiting_consent'; manifest: ScriptManifest; checks: PreflightCheck[]; sourceCode: string }
  | { phase: 'configuring_params'; param: string; before: number; after: number; rebootRequired: boolean }
  | { phase: 'rebooting'; secondsWaited: number; estimatedTotalSec: number }
  /** Quick write probe to decide whether FTP install will work at all. */
  | { phase: 'probing_capability' }
  | { phase: 'uploading'; filename: string; bytesWritten: number; bytesTotal: number }
  | { phase: 'awaiting_heartbeat'; secondsWaited: number; timeoutSec: number }
  | { phase: 'verifying'; expectedVersion: string }
  | { phase: 'success'; installedAt: string }
  /**
   * FTP write was rejected and the script can't be auto-installed. Caller
   * should download the .lua and put it on the FC's SD card manually. The
   * script will auto-register via the heartbeat watcher once the FC reboots
   * with the file in place.
   */
  | { phase: 'manual_install_needed'; manifest: ScriptManifest; ftpError: string; targetPath: string }
  | { phase: 'error'; message: string; code: InstallErrorCode; retriable: boolean };

export type InstallErrorCode =
  | 'NOT_CONNECTED'
  | 'PRECHECK_FAILED'
  | 'CONSENT_REQUIRED'
  | 'PARAM_SET_FAILED'
  | 'REBOOT_TIMED_OUT'
  | 'FTP_WRITE_FAILED'
  | 'HEARTBEAT_TIMED_OUT'
  | 'VERSION_MISMATCH'
  | 'CANCELLED'
  | 'VEHICLE_ARMED_BLOCK'
  | 'SLOT_EXHAUSTED'
  | 'UNKNOWN';

/**
 * Renderer → main IPC requests for the installer.
 */
export interface InstallerApi {
  /** Read the manifest of the script ArduDeck would install. Pure - no FC contact. */
  getManifest(): Promise<ScriptManifest>;

  /** Read the Lua source code (for the preview pane). */
  getSourceCode(): Promise<string>;

  /** Run preflight checks against the currently-connected FC. */
  runPreflight(): Promise<PreflightCheck[]>;

  /** Begin the install flow. Emits InstallPhase events on the install-state channel. */
  beginInstall(): Promise<void>;

  /** User confirmed the consent step - proceeds from awaiting_consent. */
  grantConsent(): Promise<void>;

  /** Apply a single preflight fix (e.g. set SCR_ENABLE=1, reboot). */
  applyFix(fix: PreflightFix): Promise<void>;

  /** Cancel the in-flight install. Cleanly aborts at any phase. */
  cancelInstall(): Promise<void>;

  /** Get the registry entry for the connected FC (or null if not present). */
  getRegistryForCurrentFc(): Promise<FcRegistryEntry | null>;

  /** Get all registry entries (for the audit/manage page). */
  getAllRegistryEntries(): Promise<FcRegistryEntry[]>;

  /** Remove the script and revert any made parameter changes for the connected FC. */
  uninstallFromCurrentFc(): Promise<void>;
}
