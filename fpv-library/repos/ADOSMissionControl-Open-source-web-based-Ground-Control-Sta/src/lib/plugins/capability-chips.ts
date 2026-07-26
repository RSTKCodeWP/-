/**
 * @module CapabilityChips
 * @description Derives human-readable hardware-capability chips
 *   (Camera / NPU / GPS / IMU / Thermal / LIDAR) from the raw agent
 *   permission strings a plugin manifest declares. Used by the plugin
 *   install dialog and the per-drone plugin-backed catalog view so
 *   operators can see at a glance what hardware a plugin needs.
 *
 * @license GPL-3.0-only
 */

/**
 * Stable chip identifiers. Render order in the UI follows array order:
 * Camera, NPU, GPS, IMU, Thermal, LIDAR. Extending this list is a
 * cross-stack change — the agent-side capability catalog must declare
 * the matching permission first.
 */
export type CapabilityChipId =
  | "camera"
  | "npu"
  | "gps"
  | "imu"
  | "thermal"
  | "lidar";

export interface CapabilityChip {
  id: CapabilityChipId;
  label: string;
}

const ALL_CHIPS: Readonly<Record<CapabilityChipId, CapabilityChip>> = {
  camera: { id: "camera", label: "Camera" },
  npu: { id: "npu", label: "NPU" },
  gps: { id: "gps", label: "GPS" },
  imu: { id: "imu", label: "IMU" },
  thermal: { id: "thermal", label: "Thermal" },
  lidar: { id: "lidar", label: "LIDAR" },
};

// Render order. Independent of the input permission list so a plugin
// declaring permissions in any order still gets a consistent UI.
const RENDER_ORDER: readonly CapabilityChipId[] = [
  "camera",
  "npu",
  "gps",
  "imu",
  "thermal",
  "lidar",
];

/**
 * Optional context the chip resolver can use to suppress chips that
 * make no sense on the target drone. None today is a hard requirement —
 * an installer that doesn't know about FC connection state still gets a
 * complete chip list, the operator just sees a chip for a sensor the
 * drone advertises whether or not the FC is talking back.
 */
export interface ChipDerivationContext {
  /** True when the agent reports an FC handshake. When false, GPS and
   * IMU chips drop unless a plugin explicitly declares the dedicated
   * sensor.imu.register permission (which means it owns the IMU
   * directly, not via MAVLink). */
  fcConnected?: boolean;
  /** Plugin's declared vendor-binary attribution entries. Used to
   * detect NPU vendor SDKs (rknn, tensorrt, snpe). The structure
   * matches the agent manifest's `vendor_attribution` list — each
   * entry's `name` field is matched case-insensitively against the
   * NPU vendor list. Plugins that spawn rknn_toolkit, tensorrt, etc.
   * trigger the NPU chip even without `mavlink.component.vio`. */
  vendorAttribution?: ReadonlyArray<{
    name?: string;
    license?: string;
    source_url?: string;
  }>;
}

/** Lower-cased substrings that, when present in a vendor-attribution
 * name, mean the plugin is bundling an NPU runtime. Keep this list
 * tight — false positives surface a misleading NPU chip on plugins
 * that ship a non-NPU vendor binary. */
const NPU_VENDOR_HINTS: readonly string[] = [
  "rknn",
  "tensorrt",
  "snpe",
  "openvino",
];

/**
 * Resolve the chip set for a plugin's declared permissions. The
 * input array is the wire-shape `permissions` block from the manifest:
 * each entry is the canonical capability id (e.g. "hardware.usb.uvc").
 *
 * Returns chips in `RENDER_ORDER`. Unknown permission strings are
 * ignored — the install dialog still lists them in the raw permission
 * table; chip derivation is best-effort hardware-summary surface area.
 */
export function permissionsToChips(
  permissions: readonly string[],
  context: ChipDerivationContext = {},
): CapabilityChip[] {
  const declared = new Set(permissions);
  const found = new Set<CapabilityChipId>();

  // Camera: any of the camera-binding capabilities.
  if (
    declared.has("hardware.camera.csi") ||
    declared.has("hardware.usb.uvc") ||
    declared.has("sensor.camera.register") ||
    declared.has("mavlink.component.camera")
  ) {
    found.add("camera");
  }

  // NPU: explicit estimator paths, or a vendor-attribution entry that
  // names a known NPU runtime. `process.spawn` alone is not enough —
  // a plugin can spawn a non-inference helper too. The vendor hint
  // is the load-bearing signal.
  if (declared.has("mavlink.component.vio")) {
    found.add("npu");
  } else if (
    declared.has("process.spawn") &&
    context.vendorAttribution?.some((entry) =>
      isNpuVendor(entry.name ?? ""),
    )
  ) {
    found.add("npu");
  }

  // GPS: MAVLink position telemetry is the standard surface. Requires
  // an FC handshake; without FC there is no GPS over MAVLink.
  if (
    (context.fcConnected ?? true) &&
    declared.has("telemetry.read")
  ) {
    found.add("gps");
  }

  // IMU: a plugin registering its own IMU driver always gets the chip
  // (the driver owns the IMU directly). Otherwise an FC handshake
  // implies an IMU through MAVLink.
  if (declared.has("sensor.imu.register")) {
    found.add("imu");
  } else if (
    (context.fcConnected ?? true) &&
    declared.has("telemetry.read")
  ) {
    found.add("imu");
  }

  // Thermal: a plugin claiming raw USB access is most likely binding
  // a thermal-camera UVC device (FLIR Lepton, PureThermal, etc.).
  // hardware.usb.uvc on its own falls into Camera above — this branch
  // catches the wider hardware.usb permission which is what thermal
  // shims declare when they need vendor-tool ioctls beyond UVC.
  if (
    declared.has("hardware.usb") &&
    !declared.has("hardware.usb.uvc")
  ) {
    found.add("thermal");
  }

  // LIDAR: dedicated registration permission.
  if (declared.has("sensor.lidar.register")) {
    found.add("lidar");
  }

  return RENDER_ORDER.filter((id) => found.has(id)).map((id) => ALL_CHIPS[id]);
}

function isNpuVendor(name: string): boolean {
  const lower = name.toLowerCase();
  return NPU_VENDOR_HINTS.some((hint) => lower.includes(hint));
}
