/**
 * Board catalog barrel exports.
 * @license GPL-3.0-only
 */

export {
  type ArduPilotBoardEntry,
  type ArduPilotBoardCategory,
  ARDUPILOT_BOARDS,
  findArduPilotBoard,
  inferBoardMetadata,
  getArduPilotVendors,
  groupArduPilotBoardsByVendor,
} from './ardupilot-boards'

export {
  type BetaflightBoardCatalog,
  buildBetaflightCatalog,
  buildBetaflightSelectGroups,
} from './betaflight-boards'

export {
  type PX4BoardMeta,
  PX4_BOARD_MAP,
  resolvePX4BoardMeta,
  buildPX4SelectGroups,
} from './px4-boards'
