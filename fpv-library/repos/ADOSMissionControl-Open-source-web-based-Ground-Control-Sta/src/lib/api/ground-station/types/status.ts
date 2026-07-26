/**
 * @module api/ground-station/types/status
 * @description Top-level status response shape returned by the ground agent.
 *
 * @license GPL-3.0-only
 */

import type {
  GroundStationLinkHealth,
  GroundStationStatus as GroundStationStatusState,
} from "@/stores/ground-station-store";

export interface GroundStationStatusResponse extends GroundStationStatusState {
  link_health?: Partial<GroundStationLinkHealth>;
}
