// Ground station overall status snapshot.

import type { GroundStationStatusResponse } from "./types";
import { gsRequest, type RequestContext } from "./request";

export function getStatus(ctx: RequestContext): Promise<GroundStationStatusResponse> {
  return gsRequest<GroundStationStatusResponse>(ctx, "/api/v1/ground-station/status");
}
