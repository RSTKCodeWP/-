import { describe, it, expect } from "vitest";
import { artifactRelPath, proxiedArtifactUrl } from "../compute-artifact";

describe("artifactRelPath", () => {
  it("extracts the artifacts/ path from a full engine URL, ignoring the host", () => {
    expect(
      artifactRelPath("http://some-host.local:8092/artifacts/recon-1/output.ply"),
    ).toBe("artifacts/recon-1/output.ply");
  });
  it("handles a bare path", () => {
    expect(artifactRelPath("/artifacts/ds-9/output.rrd")).toBe(
      "artifacts/ds-9/output.rrd",
    );
  });
  it("returns null when there is no artifacts/ segment (e.g. a mock:// uri)", () => {
    expect(artifactRelPath("mock://splat/1")).toBeNull();
    expect(artifactRelPath("http://h:8092/other/x")).toBeNull();
  });
});

describe("proxiedArtifactUrl", () => {
  it("routes a real artifact through the same-origin proxy at the paired host", () => {
    const out = proxiedArtifactUrl(
      "http://drifting-host.local:8092/artifacts/recon-1/output.ply",
      "example-node.local",
      "key123",
    );
    expect(out).toContain("/api/lan-pair/artifact?");
    const qs = new URLSearchParams(out.split("?")[1]);
    expect(qs.get("host")).toBe("example-node.local");
    expect(qs.get("path")).toBe("artifacts/recon-1/output.ply");
    expect(qs.get("key")).toBe("key123");
  });
  it("leaves the URL unchanged when no paired host is known", () => {
    const raw = "http://h:8092/artifacts/recon-1/output.ply";
    expect(proxiedArtifactUrl(raw, null)).toBe(raw);
    expect(proxiedArtifactUrl(raw, "")).toBe(raw);
  });
  it("leaves a non-artifact (mock) uri unchanged", () => {
    expect(proxiedArtifactUrl("mock://splat/1", "host.local")).toBe(
      "mock://splat/1",
    );
  });
});
