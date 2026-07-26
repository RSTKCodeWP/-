/**
 * @module status-mapper-install-health.test
 * @description Pins how the cloud-relay heartbeat row maps the
 * install-health + kernel/radio-module surface into AgentStatus. These
 * fields ride the same heartbeat as boardArch/boardSoc, so the mapper
 * must forward them verbatim, narrow the enum-like ones, and leave them
 * undefined when the agent omits them (older-agent safety).
 * @license GPL-3.0-only
 */

import { describe, expect, it } from "vitest";

import { mapCloudStatus } from "@/components/command/bridges/status-mapper";

const base = {
  deviceId: "dev-1",
  version: "0.39.0",
  uptimeSeconds: 600,
  updatedAt: Date.now(),
};

describe("mapCloudStatus install-health + kernel/module surface", () => {
  it("forwards a healthy heartbeat verbatim", () => {
    const out = mapCloudStatus({
      ...base,
      kernelRelease: "6.1.0-rpi7-rpi-v8",
      wfbModuleSource: "prebuilt",
      installStatus: "ok",
      installVersion: "0.39.0",
      failedSteps: [],
    });
    expect(out.kernel_release).toBe("6.1.0-rpi7-rpi-v8");
    expect(out.wfb_module_source).toBe("prebuilt");
    expect(out.install_status).toBe("ok");
    expect(out.install_version).toBe("0.39.0");
    // Empty array carries no failed steps → undefined for the renderer.
    expect(out.failed_steps).toBeUndefined();
  });

  it("carries failed steps when install is degraded", () => {
    const out = mapCloudStatus({
      ...base,
      wfbModuleSource: "dkms",
      installStatus: "degraded",
      failedSteps: ["dkms_build", "camera_probe"],
    });
    expect(out.wfb_module_source).toBe("dkms");
    expect(out.install_status).toBe("degraded");
    expect(out.failed_steps).toEqual(["dkms_build", "camera_probe"]);
  });

  it("leaves the surface undefined for an older agent that omits it", () => {
    const out = mapCloudStatus({ ...base });
    expect(out.kernel_release).toBeUndefined();
    expect(out.wfb_module_source).toBeUndefined();
    expect(out.install_status).toBeUndefined();
    expect(out.install_version).toBeUndefined();
    expect(out.failed_steps).toBeUndefined();
  });

  it("drops unknown enum values rather than passing garbage through", () => {
    const out = mapCloudStatus({
      ...base,
      wfbModuleSource: "bogus",
      installStatus: "weird",
    });
    expect(out.wfb_module_source).toBeUndefined();
    expect(out.install_status).toBeUndefined();
  });
});
