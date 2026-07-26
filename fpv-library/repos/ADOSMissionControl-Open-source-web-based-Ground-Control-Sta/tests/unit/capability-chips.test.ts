/**
 * Verifies permissionsToChips() — the wire-permission to chip-label
 * resolver that the plugin install dialog and the future plugin-backed
 * catalog use to summarise hardware requirements.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { permissionsToChips } from "@/lib/plugins/capability-chips";

describe("permissionsToChips", () => {
  it("returns empty list for a GCS-only plugin with no hardware permissions", () => {
    expect(
      permissionsToChips(["ui.slot.drone-detail-tab", "telemetry.subscribe"]),
    ).toEqual([]);
  });

  it("maps hardware.usb.uvc to a Camera chip", () => {
    const chips = permissionsToChips(["hardware.usb.uvc"]);
    expect(chips.map((c) => c.id)).toEqual(["camera"]);
  });

  it("maps hardware.camera.csi to a Camera chip", () => {
    const chips = permissionsToChips(["hardware.camera.csi"]);
    expect(chips.map((c) => c.id)).toEqual(["camera"]);
  });

  it("maps sensor.camera.register to a Camera chip", () => {
    const chips = permissionsToChips(["sensor.camera.register"]);
    expect(chips.map((c) => c.id)).toEqual(["camera"]);
  });

  it("maps mavlink.component.vio to an NPU chip", () => {
    const chips = permissionsToChips(["mavlink.component.vio"]);
    expect(chips.map((c) => c.id)).toEqual(["npu"]);
  });

  it("maps process.spawn + rknn vendor attribution to an NPU chip", () => {
    const chips = permissionsToChips(["process.spawn"], {
      vendorAttribution: [
        { name: "RKNN runtime", license: "Apache-2.0" },
      ],
    });
    expect(chips.map((c) => c.id)).toEqual(["npu"]);
  });

  it("maps process.spawn + tensorrt vendor attribution to an NPU chip", () => {
    const chips = permissionsToChips(["process.spawn"], {
      vendorAttribution: [{ name: "NVIDIA TensorRT" }],
    });
    expect(chips.map((c) => c.id)).toEqual(["npu"]);
  });

  it("does NOT add an NPU chip for process.spawn with a non-NPU vendor binary", () => {
    const chips = permissionsToChips(["process.spawn"], {
      vendorAttribution: [{ name: "libusb" }],
    });
    expect(chips).toEqual([]);
  });

  it("maps telemetry.read (FC connected default) to GPS + IMU chips", () => {
    const chips = permissionsToChips(["telemetry.read"]);
    expect(chips.map((c) => c.id)).toEqual(["gps", "imu"]);
  });

  it("drops GPS + IMU chips when FC is reported disconnected", () => {
    const chips = permissionsToChips(["telemetry.read"], {
      fcConnected: false,
    });
    expect(chips).toEqual([]);
  });

  it("maps sensor.imu.register to an IMU chip even without an FC", () => {
    const chips = permissionsToChips(["sensor.imu.register"], {
      fcConnected: false,
    });
    expect(chips.map((c) => c.id)).toEqual(["imu"]);
  });

  it("maps hardware.usb (without uvc) to a Thermal chip", () => {
    const chips = permissionsToChips(["hardware.usb"]);
    expect(chips.map((c) => c.id)).toEqual(["thermal"]);
  });

  it("does not classify hardware.usb.uvc as Thermal — only as Camera", () => {
    const chips = permissionsToChips(["hardware.usb.uvc"]);
    expect(chips.map((c) => c.id)).toEqual(["camera"]);
    expect(chips.some((c) => c.id === "thermal")).toBe(false);
  });

  it("maps sensor.lidar.register to a LIDAR chip", () => {
    const chips = permissionsToChips(["sensor.lidar.register"]);
    expect(chips.map((c) => c.id)).toEqual(["lidar"]);
  });

  it("renders chips in the canonical order (camera, npu, gps, imu, thermal, lidar)", () => {
    // Pass permissions in jumbled order so we can verify the resolver
    // imposes its own ordering rather than echoing input order.
    const chips = permissionsToChips([
      "sensor.lidar.register",
      "hardware.usb",
      "telemetry.read",
      "mavlink.component.vio",
      "hardware.camera.csi",
    ]);
    expect(chips.map((c) => c.id)).toEqual([
      "camera",
      "npu",
      "gps",
      "imu",
      "thermal",
      "lidar",
    ]);
  });

  it("deduplicates a chip when multiple permissions trigger it", () => {
    // hardware.camera.csi + hardware.usb.uvc + sensor.camera.register all
    // point at the camera. The output should list a single Camera chip,
    // not three.
    const chips = permissionsToChips([
      "hardware.camera.csi",
      "hardware.usb.uvc",
      "sensor.camera.register",
    ]);
    expect(chips.map((c) => c.id)).toEqual(["camera"]);
  });

  it("returns a stable label string for each chip", () => {
    const chips = permissionsToChips([
      "hardware.camera.csi",
      "mavlink.component.vio",
      "sensor.lidar.register",
    ]);
    expect(chips.find((c) => c.id === "camera")?.label).toBe("Camera");
    expect(chips.find((c) => c.id === "npu")?.label).toBe("NPU");
    expect(chips.find((c) => c.id === "lidar")?.label).toBe("LIDAR");
  });

  it("ignores unknown permission strings", () => {
    const chips = permissionsToChips([
      "hardware.camera.csi",
      "future.unknown.capability",
    ]);
    expect(chips.map((c) => c.id)).toEqual(["camera"]);
  });
});
