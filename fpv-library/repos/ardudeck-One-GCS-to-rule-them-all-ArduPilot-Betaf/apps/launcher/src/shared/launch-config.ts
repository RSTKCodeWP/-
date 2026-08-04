/**
 * The launch config contract.
 *
 * One versioned JSON file, written by the launcher and read by the game. It is the
 * only channel between the two: the game must never need an env var, a hardcoded
 * constant, or the launcher's presence in memory to know what to load.
 *
 * Degradation is part of the contract, not an implementation detail. A missing file, a
 * missing block or a missing field must leave the game running with a warning. That rule
 * exists because a required manifest field once aborted the whole terrain load and
 * rendered an empty world, which reads as a total failure rather than one absent value.
 * `parseLaunchConfig` below mirrors the leniency the Rust side implements, so the two can
 * be checked against the same cases.
 */

/** Bump only for a breaking change. Additive fields stay on the current version. */
export const LAUNCH_CONFIG_SCHEMA_VERSION = 1;

/** Default FPV camera uptilt, degrees. Matches the game's own default. */
export const DEFAULT_FPV_UPTILT_DEG = 25;
/** Above ~55 deg the horizon leaves the frame even in level flight. */
export const MAX_FPV_UPTILT_DEG = 55;

export interface LaunchHome {
  /** WGS84 degrees. */
  lat: number;
  lon: number;
  /** Ground elevation at home, metres AMSL. Omitted means "sample the terrain". */
  altM?: number;
  /** Initial yaw, degrees true. Omitted means the game keeps its own default. */
  headingDeg?: number;
}

export interface LaunchRegion {
  /** Directory name of the baked region, for example "bar". */
  name: string;
  /**
   * Absolute path to the baked region directory. Absolute (not `res://`) because a
   * downloaded or user-baked region will live outside the Godot project, and Godot's
   * FileAccess and Image loaders take absolute paths at runtime.
   */
  assetPath: string;
  home: LaunchHome;
}

export interface LaunchCamera {
  /** FPV camera uptilt, degrees. Clamped to 0..MAX_FPV_UPTILT_DEG. */
  fpvUptiltDeg: number;
}

/**
 * RESERVED for Phase 2 (vehicle path). Nothing writes this yet and the game must treat a
 * null or absent block as "use your defaults". The field names are a sketch of what Phase 2
 * needs, not a frozen contract: FRAME_CLASS and FRAME_TYPE are listed because the FDM's
 * motor layout has to match what the flight stack is mixing for, and carrying them here is
 * what stops an imported param file from reproducing the mixer-versus-plant divergence.
 */
export interface LaunchVehicle {
  firmware?: {
    family?: 'ardupilot' | 'inav';
    vehicle?: string;
    releaseTrack?: string;
    sitlBinPath?: string;
  };
  frame?: {
    frameClass?: number;
    frameType?: number;
    specPath?: string;
  };
  params?: {
    paramFilePath?: string;
    defaultsPath?: string;
  };
}

/**
 * RESERVED for Phase 4 (conditions as real systems). Nothing writes this yet. The game's
 * seams already exist (`AtmosphereSystem::set_time_of_day`, the weather presets), so this
 * block is only ever the thing that drives them.
 */
export interface LaunchConditions {
  time?: {
    mode?: 'current' | 'fixed';
    /** 0..1 across the day, the unit the game's sun arc already speaks. */
    timeOfDay?: number;
    /** ISO 8601, when mode is "fixed" and a real date matters for the solar position. */
    utc?: string;
  };
  weather?: {
    mode?: 'current' | 'preset';
    preset?: 'clear' | 'fair' | 'overcast' | 'storm';
    windMs?: number;
  };
}

export interface LaunchConfig {
  schemaVersion: number;
  generatedBy: { app: string; version: string };
  /** ISO 8601 UTC. Diagnostic only, so a stale config in a bug report is obvious. */
  generatedAt: string;
  region: LaunchRegion;
  camera: LaunchCamera;
  /** Phase 2 fills this. */
  vehicle: LaunchVehicle | null;
  /** Phase 4 fills this. */
  conditions: LaunchConditions | null;
}

export interface BuildLaunchConfigInput {
  region: {
    name: string;
    assetPath: string;
    home: LaunchHome;
  };
  fpvUptiltDeg?: number;
  appVersion: string;
  /** Injectable so the unit tests are not time-dependent. */
  now?: Date;
}

export function clampUptilt(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_FPV_UPTILT_DEG;
  return Math.min(MAX_FPV_UPTILT_DEG, Math.max(0, value));
}

export function buildLaunchConfig(input: BuildLaunchConfigInput): LaunchConfig {
  return {
    schemaVersion: LAUNCH_CONFIG_SCHEMA_VERSION,
    generatedBy: { app: 'ardudeck-launcher', version: input.appVersion },
    generatedAt: (input.now ?? new Date()).toISOString(),
    region: {
      name: input.region.name,
      assetPath: input.region.assetPath,
      home: input.region.home,
    },
    camera: {
      fpvUptiltDeg: clampUptilt(input.fpvUptiltDeg ?? DEFAULT_FPV_UPTILT_DEG),
    },
    vehicle: null,
    conditions: null,
  };
}

export interface ParsedLaunchConfig {
  /** Null only when the input is not an object at all. Everything else degrades. */
  config: LaunchConfig | null;
  warnings: string[];
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function finiteNumber(v: unknown): number | undefined {
  return typeof v === 'number' && Number.isFinite(v) ? v : undefined;
}

/**
 * Lenient read of a config that may have been written by another version, hand-edited, or
 * truncated. Never throws: it collects what it could not use into `warnings` and fills the
 * rest with defaults, which is the same degradation the game performs.
 */
export function parseLaunchConfig(raw: unknown): ParsedLaunchConfig {
  const warnings: string[] = [];
  if (!isRecord(raw)) {
    return { config: null, warnings: ['config root is not a JSON object'] };
  }

  const version = finiteNumber(raw.schemaVersion);
  if (version === undefined) {
    warnings.push('no schemaVersion, assuming the current one');
  } else if (version > LAUNCH_CONFIG_SCHEMA_VERSION) {
    warnings.push(
      `config schemaVersion ${version} is newer than this build understands (${LAUNCH_CONFIG_SCHEMA_VERSION}), unknown fields ignored`,
    );
  }

  const regionRaw = isRecord(raw.region) ? raw.region : undefined;
  if (!regionRaw) warnings.push('no region block, the game falls back to its default region');

  const homeRaw = regionRaw && isRecord(regionRaw.home) ? regionRaw.home : undefined;
  const lat = homeRaw ? finiteNumber(homeRaw.lat) : undefined;
  const lon = homeRaw ? finiteNumber(homeRaw.lon) : undefined;
  if (regionRaw && (lat === undefined || lon === undefined)) {
    warnings.push('region.home is missing lat/lon, the game falls back to the region manifest');
  }

  const name = regionRaw && typeof regionRaw.name === 'string' ? regionRaw.name : '';
  const assetPath = regionRaw && typeof regionRaw.assetPath === 'string' ? regionRaw.assetPath : '';
  if (regionRaw && !name && !assetPath) {
    warnings.push('region has neither name nor assetPath, nothing to load');
  }

  const cameraRaw = isRecord(raw.camera) ? raw.camera : undefined;
  const uptiltRaw = cameraRaw ? finiteNumber(cameraRaw.fpvUptiltDeg) : undefined;
  if (cameraRaw && uptiltRaw === undefined) {
    warnings.push('camera.fpvUptiltDeg is missing or not a number, using the default');
  }
  const uptilt = clampUptilt(uptiltRaw ?? DEFAULT_FPV_UPTILT_DEG);
  if (uptiltRaw !== undefined && uptilt !== uptiltRaw) {
    warnings.push(`camera.fpvUptiltDeg ${uptiltRaw} clamped to ${uptilt}`);
  }

  const home: LaunchHome = { lat: lat ?? 0, lon: lon ?? 0 };
  const altM = homeRaw ? finiteNumber(homeRaw.altM) : undefined;
  if (altM !== undefined) home.altM = altM;
  const headingDeg = homeRaw ? finiteNumber(homeRaw.headingDeg) : undefined;
  if (headingDeg !== undefined) home.headingDeg = headingDeg;

  const generatedBy = isRecord(raw.generatedBy) ? raw.generatedBy : undefined;

  return {
    config: {
      schemaVersion: version ?? LAUNCH_CONFIG_SCHEMA_VERSION,
      generatedBy: {
        app: typeof generatedBy?.app === 'string' ? generatedBy.app : 'unknown',
        version: typeof generatedBy?.version === 'string' ? generatedBy.version : 'unknown',
      },
      generatedAt: typeof raw.generatedAt === 'string' ? raw.generatedAt : '',
      region: { name, assetPath, home },
      camera: { fpvUptiltDeg: uptilt },
      vehicle: isRecord(raw.vehicle) ? (raw.vehicle as LaunchVehicle) : null,
      conditions: isRecord(raw.conditions) ? (raw.conditions as LaunchConditions) : null,
    },
    warnings,
  };
}

export function serializeLaunchConfig(config: LaunchConfig): string {
  return `${JSON.stringify(config, null, 2)}\n`;
}
