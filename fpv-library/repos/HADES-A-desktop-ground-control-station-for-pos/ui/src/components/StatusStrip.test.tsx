import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useSystemStore } from "../store/system";
import { StatusStrip } from "./StatusStrip";

describe("StatusStrip", () => {
  beforeEach(() => {
    useSystemStore.getState().reset();
  });

  it("always shows the trust fields (link / telemetry / GPS / clock) — never hidden", () => {
    render(<StatusStrip clock="14:22:07Z" />);
    expect(screen.getByTestId("strip-link")).toBeInTheDocument();
    expect(screen.getByTestId("strip-telemetry")).toBeInTheDocument();
    expect(screen.getByTestId("strip-gps")).toBeInTheDocument();
    expect(screen.getByText("14:22:07Z")).toBeInTheDocument();
  });

  it("shows LINK OK in the nominal color when the link is up", () => {
    render(<StatusStrip clock="00:00:00Z" />);
    const link = screen.getByTestId("strip-link");
    expect(link).toHaveTextContent(/LINK OK/i);
    expect(link.className).toContain("text-st-nominal");
  });

  it("P0: link-lost flips to CRITICAL (magenta), not warning (orange)", () => {
    useSystemStore.getState().setLink(false);
    render(<StatusStrip clock="00:00:00Z" />);
    const link = screen.getByTestId("strip-link");
    expect(link).toHaveTextContent(/LINK LOST/i);
    expect(link.className).toContain("text-st-critical");
    expect(link.className).not.toContain("text-st-warning");
  });

  it("escalates telemetry color as it goes stale", () => {
    useSystemStore.getState().setTelemetryAge(6);
    render(<StatusStrip clock="00:00:00Z" />);
    expect(screen.getByTestId("strip-telemetry").className).toContain("text-st-stale");
  });

  it("renders the GPS fix + satellite count", () => {
    useSystemStore.getState().setGps("3d", 11);
    render(<StatusStrip clock="00:00:00Z" />);
    expect(screen.getByTestId("strip-gps")).toHaveTextContent(/3D/i);
    expect(screen.getByTestId("strip-gps")).toHaveTextContent("11");
  });

  it("shows a heartbeat indicator", () => {
    render(<StatusStrip clock="00:00:00Z" />);
    expect(screen.getByTestId("strip-heartbeat")).toBeInTheDocument();
  });
});
