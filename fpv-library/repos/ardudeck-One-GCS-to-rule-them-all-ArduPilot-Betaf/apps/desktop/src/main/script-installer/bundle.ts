/**
 * ArduDeck script bundle - inlines the Lua source at build time and computes
 * the manifest the installer + UI both reference. The SHA256 over the actual
 * source bytes is what we show in the preview, so users can verify the code
 * they see is exactly what we'll write to the FC.
 */

// Vite ?raw import: bundles the file contents as a string at build time.
// Works in main + preload bundles since electron-vite uses Vite under the hood.
import luaSource from '../lua-scripts/ardudeck_commands.lua?raw';
import { buildScriptBundle, type ScriptBundle } from './installer-service';
import { USER_CMD, SUB_CMD, type ScriptManifest } from '../../shared/script-installer-types';

const FILENAME = 'ardudeck_commands.lua';
const VERSION = '1.0.0';

let cached: ScriptBundle | null = null;

/** Build the script bundle from the inlined source. Cached after first call. */
export function getScriptBundle(): ScriptBundle {
  if (cached) return cached;

  // Manifest mirrors what's documented in the .lua header. Keep these in sync
  // when bumping the script version.
  const partialManifest: Omit<ScriptManifest, 'sha256' | 'sizeBytes'> = {
    filename: FILENAME,
    version: VERSION,
    requirements: [
      {
        param: 'SCR_ENABLE',
        why: 'Lua scripting must be enabled on the autopilot.',
        exact: 1,
        rebootIfChanged: true,
      },
      {
        param: 'SCR_HEAP_SIZE',
        why: 'Scripts need at least 64 KiB of heap.',
        min: 65536,
        rebootIfChanged: true,
      },
    ],
    commands: [
      {
        name: 'ORBIT',
        label: 'Orbit',
        description:
          'Orbits a target lat/lon at a chosen radius and altitude in GUIDED mode. Anchored to live telemetry, so link drops do not desync the orbit. Optional revolutions count: 0 = indefinite, N = stop and hover after N full circles.',
        trigger: USER_CMD.AD,
        subId: SUB_CMD.ORBIT,
        paramSchema:
          'param1=radius (m, signed; +CW, -CCW)  param2=speed (m/s, 0=default)  param3=revolutions (0=infinite)  param4=sub_id (0)  x=lat*1e7  y=lon*1e7  z=altitude (m, relative)',
      },
      {
        name: 'SPIRAL',
        label: 'Spiral',
        description:
          'Orbits a target lat/lon while continuously climbing or descending toward a target altitude at a chosen rate. Once the target altitude is reached, holds the orbit indefinitely. Useful for clearing obstacles before RTL or controlled descent into landing zones.',
        trigger: USER_CMD.AD,
        subId: SUB_CMD.SPIRAL,
        paramSchema:
          'param1=radius (m, signed; +CW, -CCW)  param2=speed (m/s, 0=default)  param3=climb_rate (m/s)  param4=sub_id (1)  x=lat*1e7  y=lon*1e7  z=target_altitude (m, relative)',
      },
      {
        name: 'WATCHTOWER',
        label: 'Watchtower',
        description:
          'Hovers at a clicked point and slowly rotates yaw for a panoramic survey. Useful for "what is around me?" site checks or quick 360° captures.',
        trigger: USER_CMD.AD,
        subId: SUB_CMD.WATCHTOWER,
        paramSchema:
          'param1=yaw_rate (deg/s, signed; +CW, -CCW; default 30)  param4=sub_id (3)  x=lat*1e7  y=lon*1e7  z=altitude (m, relative)',
      },
      {
        name: 'CLIMB_RTL',
        label: 'Climb + RTL',
        description:
          'Climbs the vehicle in place to a safe altitude before the FC switches to RTL for the actual return. Solves the "RTL into a tree" problem when current altitude is below RTL_ALT or the home path is blocked.',
        trigger: USER_CMD.AD,
        subId: SUB_CMD.CLIMB_RTL,
        paramSchema:
          'z=safe_altitude (m, relative; vehicle uses its own current lat/lon as climb anchor)  param4=sub_id (4)',
      },
      {
        name: 'REVEAL',
        label: 'Reveal',
        description:
          'Cinematic pull-back: vehicle retreats from its current position along the away-from-target bearing while climbing, yaw locked to the clicked target throughout. The "castle reveal" shot.',
        trigger: USER_CMD.AD,
        subId: SUB_CMD.REVEAL,
        paramSchema:
          'param1=pullback_distance (m)  param2=climb_amount (m, signed)  param3=speed (m/s, 0=3 default)  param4=sub_id (5)  x=lat*1e7  y=lon*1e7  z=target_alt (m, informational)',
      },
      {
        name: 'STRAFE',
        label: 'Strafe',
        description:
          'Cinematic dolly pass: vehicle flies along an axis perpendicular to the target-to-vehicle bearing at a chosen offset, yaw locked to the clicked target. Picks the side of the target the vehicle is already on so the approach is short.',
        trigger: USER_CMD.AD,
        subId: SUB_CMD.STRAFE,
        paramSchema:
          'param1=offset_distance (m, perpendicular clearance)  param2=strafe_length (m, total)  param3=speed (m/s, 0=3 default)  param4=sub_id (6)  x=lat*1e7  y=lon*1e7  z=altitude (m, relative)',
      },
      {
        name: 'LAND_AT',
        label: 'Land at point',
        description:
          'Flies to the clicked lat/lon at the vehicle\'s current altitude, then switches to LAND mode. Solves the "ArduCopter NAV_LAND ignores lat/lon and just descends in place" problem by repositioning first.',
        trigger: USER_CMD.AD,
        subId: SUB_CMD.LAND_AT,
        paramSchema:
          'x=lat*1e7  y=lon*1e7  z=approach_altitude (m, relative; 0 = current alt)  param4=sub_id (7)',
      },
    ],
    heartbeat: { name: 'AD_HB', intervalSec: 1 },
  };

  cached = buildScriptBundle(luaSource, partialManifest);
  return cached;
}
