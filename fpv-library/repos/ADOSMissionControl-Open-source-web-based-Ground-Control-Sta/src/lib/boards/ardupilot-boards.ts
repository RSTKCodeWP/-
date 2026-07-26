// Exempt from 300 LOC soft rule: pure board registry data table
/**
 * ArduPilot board registry with vendor/MCU metadata and optional timer group data.
 *
 * Timer group data is only included for verified boards.
 *
 * @license GPL-3.0-only
 */

// ── Types ────────────────────────────────────────────────────

export type ArduPilotBoardCategory = 'pixhawk' | 'mini-fc' | 'wing-fc' | 'carrier' | 'linux' | 'other'

export interface ArduPilotBoardEntry {
  name: string
  displayName: string
  vendor: string
  mcu: string
  category: ArduPilotBoardCategory
  boardIds: number[]
  outputCount?: number
  timerGroups?: number[][]
  protocols?: ('PWM' | 'DShot' | 'Both')[]
  outputNotes?: Record<number, string>
}

// ── Board Registry ──────────────────────────────────────────

export const ARDUPILOT_BOARDS: ArduPilotBoardEntry[] = [
  // ── SpeedyBee ─────────────────────────────────────────────
  {
    name: 'SpeedyBeef405Wing',
    displayName: 'SpeedyBee F405 Wing',
    vendor: 'SpeedyBee',
    mcu: 'STM32F405',
    category: 'wing-fc',
    boardIds: [1032],
    outputCount: 12,
    timerGroups: [[1, 2], [3, 4], [5, 6, 7], [8, 9, 10], [11, 12]],
    outputNotes: {
      9: 'Solder pad (S9)',
      10: 'Solder pad (S10)',
      11: 'Solder pad (S11)',
      12: 'Solder pad (S12) — default serial LED',
    },
    protocols: ['Both', 'Both', 'Both', 'Both', 'Both'],
  },
  {
    name: 'SpeedyBeef405V3',
    displayName: 'SpeedyBee F405 V3',
    vendor: 'SpeedyBee',
    mcu: 'STM32F405',
    category: 'mini-fc',
    boardIds: [1031],
    outputCount: 9,
    timerGroups: [[1, 2], [3, 4], [5, 6], [7, 8], [9]],
    outputNotes: { 9: 'LED pad — serial LED default' },
    protocols: ['Both', 'Both', 'Both', 'Both', 'PWM'],
  },
  {
    name: 'SpeedyBeef405V4',
    displayName: 'SpeedyBee F405 V4',
    vendor: 'SpeedyBee',
    mcu: 'STM32F405',
    category: 'mini-fc',
    boardIds: [1043],
    outputCount: 10,
    timerGroups: [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]],
    outputNotes: { 9: 'Solder pad', 10: 'LED pad — serial LED default' },
    protocols: ['Both', 'Both', 'Both', 'Both', 'Both'],
  },
  {
    name: 'SpeedyBeef7V3',
    displayName: 'SpeedyBee F7 V3',
    vendor: 'SpeedyBee',
    mcu: 'STM32F745',
    category: 'mini-fc',
    boardIds: [1045],
  },

  // ── Matek ─────────────────────────────────────────────────
  {
    name: 'MatekH743',
    displayName: 'Matek H743 Wing V2',
    vendor: 'Matek',
    mcu: 'STM32H743',
    category: 'wing-fc',
    boardIds: [1013],
    outputCount: 12,
    timerGroups: [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10], [11, 12]],
    outputNotes: { 11: 'S11 — solder pad', 12: 'S12 — LED pad' },
    protocols: ['Both', 'Both', 'Both', 'Both', 'Both', 'PWM'],
  },
  {
    name: 'MatekF405-SE',
    displayName: 'Matek F405-SE',
    vendor: 'Matek',
    mcu: 'STM32F405',
    category: 'mini-fc',
    boardIds: [1022],
  },
  {
    name: 'MatekF405-Wing',
    displayName: 'Matek F405-Wing',
    vendor: 'Matek',
    mcu: 'STM32F405',
    category: 'wing-fc',
    boardIds: [1053],
  },
  {
    name: 'MatekF765-Wing',
    displayName: 'Matek F765-Wing',
    vendor: 'Matek',
    mcu: 'STM32F765',
    category: 'wing-fc',
    boardIds: [1014],
  },
  {
    name: 'MatekH743-Mini',
    displayName: 'Matek H743-Mini',
    vendor: 'Matek',
    mcu: 'STM32H743',
    category: 'mini-fc',
    boardIds: [1044],
  },
  {
    name: 'MatekH743-Slim',
    displayName: 'Matek H743-Slim',
    vendor: 'Matek',
    mcu: 'STM32H743',
    category: 'mini-fc',
    boardIds: [1058],
  },

  // ── Holybro ───────────────────────────────────────────────
  {
    name: 'Pixhawk4',
    displayName: 'Pixhawk 4',
    vendor: 'Holybro',
    mcu: 'STM32F765',
    category: 'pixhawk',
    boardIds: [50],
    outputCount: 16,
    timerGroups: [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]],
    outputNotes: {
      9: 'AUX 1', 10: 'AUX 2', 11: 'AUX 3', 12: 'AUX 4',
      13: 'AUX 5', 14: 'AUX 6', 15: 'AUX 7', 16: 'AUX 8',
    },
    protocols: ['Both', 'Both', 'Both', 'Both'],
  },
  {
    name: 'Pixhawk6C',
    displayName: 'Pixhawk 6C',
    vendor: 'Holybro',
    mcu: 'STM32H743',
    category: 'pixhawk',
    boardIds: [56],
    outputCount: 16,
    timerGroups: [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]],
    outputNotes: {
      9: 'AUX 1', 10: 'AUX 2', 11: 'AUX 3', 12: 'AUX 4',
      13: 'AUX 5', 14: 'AUX 6', 15: 'AUX 7', 16: 'AUX 8',
    },
    protocols: ['Both', 'Both', 'Both', 'Both'],
  },
  {
    name: 'Pixhawk6X',
    displayName: 'Pixhawk 6X',
    vendor: 'Holybro',
    mcu: 'STM32H753',
    category: 'pixhawk',
    boardIds: [57],
    outputCount: 16,
    timerGroups: [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]],
    outputNotes: {
      9: 'AUX 1', 10: 'AUX 2', 11: 'AUX 3', 12: 'AUX 4',
      13: 'AUX 5', 14: 'AUX 6', 15: 'AUX 7', 16: 'AUX 8',
    },
    protocols: ['Both', 'Both', 'Both', 'Both'],
  },
  {
    name: 'KakuteF7',
    displayName: 'Holybro Kakute F7',
    vendor: 'Holybro',
    mcu: 'STM32F745',
    category: 'mini-fc',
    boardIds: [1012],
  },
  {
    name: 'KakuteH7',
    displayName: 'Holybro Kakute H7',
    vendor: 'Holybro',
    mcu: 'STM32H743',
    category: 'mini-fc',
    boardIds: [1046],
  },
  {
    name: 'KakuteH7Mini',
    displayName: 'Holybro Kakute H7 Mini',
    vendor: 'Holybro',
    mcu: 'STM32H743',
    category: 'mini-fc',
    boardIds: [1069],
  },
  {
    name: 'Durandal',
    displayName: 'Holybro Durandal',
    vendor: 'Holybro',
    mcu: 'STM32H743',
    category: 'pixhawk',
    boardIds: [1072],
  },

  // ── CubePilot ─────────────────────────────────────────────
  {
    name: 'CubeBlack',
    displayName: 'CubeBlack',
    vendor: 'CubePilot',
    mcu: 'STM32F427',
    category: 'pixhawk',
    boardIds: [9],
  },
  {
    name: 'CubeOrange',
    displayName: 'CubeOrange',
    vendor: 'CubePilot',
    mcu: 'STM32H743',
    category: 'pixhawk',
    boardIds: [140],
  },
  {
    name: 'CubeOrangePlus',
    displayName: 'CubeOrange+',
    vendor: 'CubePilot',
    mcu: 'STM32H743',
    category: 'pixhawk',
    boardIds: [1062],
  },
  {
    name: 'CubeYellow',
    displayName: 'CubeYellow',
    vendor: 'CubePilot',
    mcu: 'STM32F777',
    category: 'pixhawk',
    boardIds: [120],
  },

  // ── CUAV ──────────────────────────────────────────────────
  {
    name: 'CUAVv5plus',
    displayName: 'CUAV V5+',
    vendor: 'CUAV',
    mcu: 'STM32F765',
    category: 'pixhawk',
    boardIds: [1054],
  },
  {
    name: 'CUAVX7',
    displayName: 'CUAV X7',
    vendor: 'CUAV',
    mcu: 'STM32H743',
    category: 'pixhawk',
    boardIds: [1061],
  },
  {
    name: 'CUAVNora',
    displayName: 'CUAV Nora',
    vendor: 'CUAV',
    mcu: 'STM32H743',
    category: 'pixhawk',
    boardIds: [1059],
  },

  // ── mRo ───────────────────────────────────────────────────
  {
    name: 'mRoPixracer',
    displayName: 'mRo Pixracer',
    vendor: 'mRo',
    mcu: 'STM32F427',
    category: 'mini-fc',
    boardIds: [11],
  },
  {
    name: 'mRoControlZero',
    displayName: 'mRo Control Zero',
    vendor: 'mRo',
    mcu: 'STM32H743',
    category: 'mini-fc',
    boardIds: [1063],
  },
  {
    name: 'mRoControlZeroH7',
    displayName: 'mRo Control Zero H7 OEM',
    vendor: 'mRo',
    mcu: 'STM32H743',
    category: 'mini-fc',
    boardIds: [1085],
  },
  {
    name: 'mRoNexus',
    displayName: 'mRo Nexus',
    vendor: 'mRo',
    mcu: 'STM32H743',
    category: 'carrier',
    boardIds: [1093],
  },

  // ── Flywoo ────────────────────────────────────────────────
  {
    name: 'FlywooF405Pro',
    displayName: 'Flywoo F405 Pro',
    vendor: 'Flywoo',
    mcu: 'STM32F405',
    category: 'mini-fc',
    boardIds: [1039],
  },
  {
    name: 'FlywooF745',
    displayName: 'Flywoo F745',
    vendor: 'Flywoo',
    mcu: 'STM32F745',
    category: 'mini-fc',
    boardIds: [1049],
  },

  // ── iFlight ───────────────────────────────────────────────
  {
    name: 'BeastF7',
    displayName: 'iFlight Beast F7',
    vendor: 'iFlight',
    mcu: 'STM32F745',
    category: 'mini-fc',
    boardIds: [1033],
  },
  {
    name: 'BeastH7',
    displayName: 'iFlight Beast H7',
    vendor: 'iFlight',
    mcu: 'STM32H743',
    category: 'mini-fc',
    boardIds: [1064],
  },

  // ── Foxeer ────────────────────────────────────────────────
  {
    name: 'FoxeerH743V1',
    displayName: 'Foxeer H743 V1',
    vendor: 'Foxeer',
    mcu: 'STM32H743',
    category: 'mini-fc',
    boardIds: [1070],
  },

  // ── Generic / Popular boards ──────────────────────────────
  {
    name: 'OmnibusF4',
    displayName: 'Omnibus F4',
    vendor: 'Airbot',
    mcu: 'STM32F405',
    category: 'mini-fc',
    boardIds: [1002],
  },
  {
    name: 'KakuteF4',
    displayName: 'Kakute F4',
    vendor: 'Holybro',
    mcu: 'STM32F405',
    category: 'mini-fc',
    boardIds: [1011],
  },
  {
    name: 'BetaflightF4',
    displayName: 'BetaflightF4',
    vendor: 'Generic',
    mcu: 'STM32F405',
    category: 'mini-fc',
    boardIds: [1017],
  },
  {
    name: 'f4by',
    displayName: 'Swift F4BY',
    vendor: 'Swift',
    mcu: 'STM32F405',
    category: 'mini-fc',
    boardIds: [1010],
  },
  {
    name: 'MambaF405-2022',
    displayName: 'Mamba F405 2022',
    vendor: 'Diatone',
    mcu: 'STM32F405',
    category: 'mini-fc',
    boardIds: [1047],
  },
  {
    name: 'MambaH743v4',
    displayName: 'Mamba H743 V4',
    vendor: 'Diatone',
    mcu: 'STM32H743',
    category: 'mini-fc',
    boardIds: [1073],
  },

  // ── Linux boards ──────────────────────────────────────────
  {
    name: 'linux',
    displayName: 'Linux (Generic)',
    vendor: 'Generic',
    mcu: 'Linux',
    category: 'linux',
    boardIds: [70],
  },
  {
    name: 'navigator',
    displayName: 'Blue Robotics Navigator',
    vendor: 'Blue Robotics',
    mcu: 'Linux (RPi)',
    category: 'linux',
    boardIds: [100],
  },
  {
    name: 'Pixhawk1-1M',
    displayName: 'Pixhawk 1 (1M)',
    vendor: 'mRo',
    mcu: 'STM32F427',
    category: 'pixhawk',
    boardIds: [5],
  },
  {
    name: 'Pixhawk1-1M-bdshot',
    displayName: 'Pixhawk 1 (BDShot)',
    vendor: 'mRo',
    mcu: 'STM32F427',
    category: 'pixhawk',
    boardIds: [5],
  },

  // ── Generic F405 fallback ─────────────────────────────────
  {
    name: 'GenericF405',
    displayName: 'Generic F405',
    vendor: 'Generic',
    mcu: 'STM32F405',
    category: 'other',
    boardIds: [],
    outputCount: 8,
    timerGroups: [[1, 2], [3, 4], [5, 6], [7, 8]],
    outputNotes: {},
    protocols: ['Both', 'Both', 'Both', 'Both'],
  },
]

// ── Lookup indexes ──────────────────────────────────────────

const _boardIdIndex = new Map<number, ArduPilotBoardEntry>()
for (const entry of ARDUPILOT_BOARDS) {
  for (const id of entry.boardIds) {
    _boardIdIndex.set(id, entry)
  }
}

/** Find an ArduPilot board entry by AP_FW_BOARD_ID. */
export function findArduPilotBoard(boardId: number): ArduPilotBoardEntry | undefined {
  return _boardIdIndex.get(boardId)
}

// ── Vendor inference for unregistered boards ────────────────

const VENDOR_PATTERNS: [RegExp, string][] = [
  [/^SpeedyBee/i, 'SpeedyBee'],
  [/^Matek/i, 'Matek'],
  [/^Pixhawk/i, 'Holybro'],
  [/^Kakute/i, 'Holybro'],
  [/^Durandal/i, 'Holybro'],
  [/^Cube/i, 'CubePilot'],
  [/^CUAV/i, 'CUAV'],
  [/^mRo/i, 'mRo'],
  [/^Flywoo/i, 'Flywoo'],
  [/^iFlight|^Beast/i, 'iFlight'],
  [/^Foxeer/i, 'Foxeer'],
  [/^Mamba|^Diatone/i, 'Diatone'],
  [/^Omnibus/i, 'Airbot'],
  [/^JHEMCU/i, 'JHEMCU'],
  [/^Aocoda/i, 'Aocoda'],
  [/^SkystarsH7/i, 'Skystars'],
]

const MCU_PATTERNS: [RegExp, string][] = [
  [/H743|H753/i, 'STM32H743'],
  [/H757/i, 'STM32H757'],
  [/F765/i, 'STM32F765'],
  [/F745|F7[^0-9]/i, 'STM32F745'],
  [/F427|F4[^0-9]*Pro/i, 'STM32F427'],
  [/F405/i, 'STM32F405'],
  [/F303/i, 'STM32F303'],
]

/** Infer vendor and MCU from a board name string (e.g., "MatekH743" -> Matek, STM32H743). */
export function inferBoardMetadata(boardName: string): { vendor: string; mcu: string } {
  let vendor = 'Unknown'
  let mcu = 'Unknown'

  for (const [pattern, v] of VENDOR_PATTERNS) {
    if (pattern.test(boardName)) {
      vendor = v
      break
    }
  }

  for (const [pattern, m] of MCU_PATTERNS) {
    if (pattern.test(boardName)) {
      mcu = m
      break
    }
  }

  return { vendor, mcu }
}

/** Get all unique vendors from the registry. */
export function getArduPilotVendors(): string[] {
  const vendors = new Set(ARDUPILOT_BOARDS.map((b) => b.vendor))
  return Array.from(vendors).sort()
}

/** Group boards by vendor. */
export function groupArduPilotBoardsByVendor(): Map<string, ArduPilotBoardEntry[]> {
  const map = new Map<string, ArduPilotBoardEntry[]>()
  for (const board of ARDUPILOT_BOARDS) {
    const list = map.get(board.vendor) ?? []
    list.push(board)
    map.set(board.vendor, list)
  }
  return map
}
