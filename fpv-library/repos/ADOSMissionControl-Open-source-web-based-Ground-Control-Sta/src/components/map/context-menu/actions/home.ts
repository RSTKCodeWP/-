/**
 * @module map/context-menu/actions/home
 * @description Home and EKF origin action handlers. The set-home action goes
 * through a confirmation sub-panel; this handler is invoked from the panel
 * confirm button.
 * @license GPL-3.0-only
 */

import type { DroneProtocol } from "@/lib/protocol/types";
import type { MenuPosition } from "../types";

interface HomeArgs {
  protocol: DroneProtocol | null;
  menuPos: MenuPosition;
}

export function handleSetHomeConfirmed({ protocol, menuPos }: HomeArgs): void {
  if (!protocol) return;
  protocol.setHome(false, menuPos.lat, menuPos.lon, 0);
}

export function handleSetEkfOrigin({ protocol, menuPos }: HomeArgs): void {
  if (!protocol?.setEkfOrigin) return;
  protocol.setEkfOrigin(menuPos.lat, menuPos.lon, 0);
}
