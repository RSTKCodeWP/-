/**
 * Calibration MAVLink v2 message decoders: MagCalProgress, MagCalReport.
 *
 * @module protocol/messages/calibration
 */

// ── MAG_CAL_PROGRESS (ID 191) ───────────────────────────────

export interface MagCalProgressMsg {
  compassId: number;
  calMask: number;
  calStatus: number;
  attempt: number;
  completionPct: number;
  completionMask: Uint8Array;
  directionX: number;
  directionY: number;
  directionZ: number;
}

/**
 * Decode MAG_CAL_PROGRESS (msg ID 191).
 *
 * | Offset | Type       | Field           |
 * |--------|------------|-----------------|
 * | 0      | float32    | directionX      |
 * | 4      | float32    | directionY      |
 * | 8      | float32    | directionZ      |
 * | 12     | uint8      | compassId       |
 * | 13     | uint8      | calMask         |
 * | 14     | uint8      | calStatus       |
 * | 15     | uint8      | attempt         |
 * | 16     | uint8      | completionPct   |
 * | 17     | uint8[10]  | completionMask  |
 */
export function decodeMagCalProgress(dv: DataView): MagCalProgressMsg {
  const completionMask = new Uint8Array(10);
  for (let i = 0; i < 10; i++) {
    completionMask[i] = dv.getUint8(17 + i);
  }
  return {
    directionX: dv.getFloat32(0, true),
    directionY: dv.getFloat32(4, true),
    directionZ: dv.getFloat32(8, true),
    compassId: dv.getUint8(12),
    calMask: dv.getUint8(13),
    calStatus: dv.getUint8(14),
    attempt: dv.getUint8(15),
    completionPct: dv.getUint8(16),
    completionMask,
  };
}

// ── MAG_CAL_REPORT (ID 192) ────────────────────────────────

export interface MagCalReportMsg {
  compassId: number;
  calMask: number;
  calStatus: number;
  autosaved: number;
  fitness: number;
  ofsX: number;
  ofsY: number;
  ofsZ: number;
  diagX: number;
  diagY: number;
  diagZ: number;
  offdiagX: number;
  offdiagY: number;
  offdiagZ: number;
  orientationConfidence: number;
  oldOrientation: number;
  newOrientation: number;
  scaleFactor: number;
}

/**
 * Decode MAG_CAL_REPORT (msg ID 192).
 *
 * Base fields (44 bytes):
 * | Offset | Type    | Field       |
 * |--------|---------|-------------|
 * | 0      | float32 | fitness     |
 * | 4      | float32 | ofsX        |
 * | 8      | float32 | ofsY        |
 * | 12     | float32 | ofsZ        |
 * | 16     | float32 | diagX       |
 * | 20     | float32 | diagY       |
 * | 24     | float32 | diagZ       |
 * | 28     | float32 | offdiagX    |
 * | 32     | float32 | offdiagY    |
 * | 36     | float32 | offdiagZ    |
 * | 40     | uint8   | compassId   |
 * | 41     | uint8   | calMask     |
 * | 42     | uint8   | calStatus   |
 * | 43     | uint8   | autosaved   |
 *
 * Extension fields (offsets 44-53, present when payload > 44 bytes):
 * | 44     | float32 | orientationConfidence |
 * | 48     | uint8   | oldOrientation        |
 * | 49     | uint8   | newOrientation        |
 * | 50     | float32 | scaleFactor           |
 */
export function decodeMagCalReport(dv: DataView): MagCalReportMsg {
  const hasExtensions = dv.byteLength >= 54;
  return {
    fitness: dv.getFloat32(0, true),
    ofsX: dv.getFloat32(4, true),
    ofsY: dv.getFloat32(8, true),
    ofsZ: dv.getFloat32(12, true),
    diagX: dv.getFloat32(16, true),
    diagY: dv.getFloat32(20, true),
    diagZ: dv.getFloat32(24, true),
    offdiagX: dv.getFloat32(28, true),
    offdiagY: dv.getFloat32(32, true),
    offdiagZ: dv.getFloat32(36, true),
    compassId: dv.getUint8(40),
    calMask: dv.getUint8(41),
    calStatus: dv.getUint8(42),
    autosaved: dv.getUint8(43),
    orientationConfidence: hasExtensions ? dv.getFloat32(44, true) : 0,
    oldOrientation: hasExtensions ? dv.getUint8(48) : 0,
    newOrientation: hasExtensions ? dv.getUint8(49) : 0,
    scaleFactor: hasExtensions ? dv.getFloat32(50, true) : 0,
  };
}
