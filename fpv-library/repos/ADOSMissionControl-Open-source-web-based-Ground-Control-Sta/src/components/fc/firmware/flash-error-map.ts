/**
 * Maps a raw flash error into a category + an actionable remedy (plain
 * sentence, numbered recovery steps, a primary action, and whether to show
 * the manual-bootloader guide). Keeps the error-handling logic out of the UI
 * and the flash hook, and unit-testable in isolation.
 *
 * @module fc/firmware/flash-error-map
 */

import type { FlashErrorCategory } from "@/stores/flash-log-store";

export type FlashRemedyAction = "retry" | "retry-lower-baud" | "select-bootloader";

export interface FlashRemedy {
  category: FlashErrorCategory;
  /** i18n key under `flashTool.errors`. */
  titleKey: string;
  /** i18n keys under `flashTool.errors` for the numbered recovery steps. */
  stepKeys: string[];
  primaryAction?: FlashRemedyAction;
  showManualBootloader: boolean;
}

/** Classify a thrown error into a stable category. */
export function categorize(err: unknown): FlashErrorCategory {
  const name = err instanceof DOMException ? err.name : "";
  const msg = (err instanceof Error ? err.message : String(err ?? "")).toLowerCase();

  if (msg.includes("abort")) return "aborted";
  if (
    name === "NetworkError" ||
    msg.includes("disconnect") ||
    msg.includes("re-enumerat") ||
    msg.includes("device has been lost") ||
    msg.includes("read ended")
  ) {
    return "device_disconnected";
  }
  if (name === "SecurityError" || msg.includes("webusb blocked") || msg.includes("secure context")) {
    return "webusb_blocked";
  }
  if (msg.includes("not supported") && (msg.includes("web serial") || msg.includes("webusb"))) {
    return "browser_unsupported";
  }
  if (name === "NotFoundError" || msg.includes("no device") || msg.includes("no port selected")) {
    return "no_device";
  }
  if (msg.includes("board id mismatch")) return "board_id_mismatch";
  if (msg.includes("crc")) return "crc_mismatch";
  if (msg.includes("synchronize") || msg.includes("sync") || msg.includes("timeout")) {
    return "sync_timeout";
  }
  return "unknown";
}

const REMEDIES: Record<FlashErrorCategory, Omit<FlashRemedy, "category">> = {
  device_disconnected: {
    titleKey: "deviceDisconnected.title",
    stepKeys: ["deviceDisconnected.step1", "deviceDisconnected.step2"],
    primaryAction: "select-bootloader",
    showManualBootloader: true,
  },
  sync_timeout: {
    titleKey: "syncTimeout.title",
    stepKeys: ["syncTimeout.step1", "syncTimeout.step2", "syncTimeout.step3"],
    primaryAction: "retry",
    showManualBootloader: true,
  },
  board_id_mismatch: {
    titleKey: "boardIdMismatch.title",
    stepKeys: ["boardIdMismatch.step1"],
    showManualBootloader: false,
  },
  crc_mismatch: {
    titleKey: "crcMismatch.title",
    stepKeys: ["crcMismatch.step1", "crcMismatch.step2"],
    primaryAction: "retry",
    showManualBootloader: false,
  },
  webusb_blocked: {
    titleKey: "webusbBlocked.title",
    stepKeys: ["webusbBlocked.step1"],
    showManualBootloader: false,
  },
  no_device: {
    titleKey: "noDevice.title",
    stepKeys: ["noDevice.step1"],
    primaryAction: "retry",
    showManualBootloader: true,
  },
  browser_unsupported: {
    titleKey: "browserUnsupported.title",
    stepKeys: ["browserUnsupported.step1"],
    showManualBootloader: false,
  },
  aborted: {
    titleKey: "aborted.title",
    stepKeys: [],
    primaryAction: "retry",
    showManualBootloader: false,
  },
  unknown: {
    titleKey: "unknown.title",
    stepKeys: ["unknown.step1"],
    primaryAction: "retry",
    showManualBootloader: true,
  },
};

/** Build the remedy descriptor for a category. */
export function mapError(category: FlashErrorCategory): FlashRemedy {
  return { category, ...REMEDIES[category] };
}
