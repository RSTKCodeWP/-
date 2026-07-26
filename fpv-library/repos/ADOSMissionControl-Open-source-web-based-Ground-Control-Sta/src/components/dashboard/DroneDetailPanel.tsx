/**
 * @module DroneDetailPanel
 * @description Compatibility re-export. The unified per-node detail panel is
 * now NodeDetailPanel (profile-aware surface registry under ./node-detail/).
 * This barrel keeps the historical import path working.
 * @license GPL-3.0-only
 */

export {
  NodeDetailPanel,
  NodeDetailPanel as DroneDetailPanel,
} from "./node-detail/NodeDetailPanel";
