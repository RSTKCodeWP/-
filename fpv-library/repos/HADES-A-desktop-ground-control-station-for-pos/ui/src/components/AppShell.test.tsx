import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "./AppShell";

/* The OPS-mode fixed-grid layout (impl-plan Task 5.3; DESIGN-SYSTEM §7.1): a map-primary region,
 * a list rail, a docked video panel, and a mission-log foot. The status strip moved UP into the
 * console frame (§11.4 — it persists across modes), so it is no longer an AppShell slot. Regions
 * are addressed by slot so component tasks fill them without touching the grid. */

describe("AppShell", () => {
  const slots = {
    map: <div data-testid="slot-map">map</div>,
    list: <div data-testid="slot-list">list</div>,
    video: <div data-testid="slot-video">video</div>,
    missionLog: <div data-testid="slot-log">log</div>,
  };

  it("renders all four regions of the fixed grid", () => {
    render(<AppShell {...slots} />);
    expect(screen.getByTestId("slot-map")).toBeInTheDocument();
    expect(screen.getByTestId("slot-list")).toBeInTheDocument();
    expect(screen.getByTestId("slot-video")).toBeInTheDocument();
    expect(screen.getByTestId("slot-log")).toBeInTheDocument();
  });

  it("gives each region a labelled landmark for keyboard/AT navigation", () => {
    render(<AppShell {...slots} />);
    expect(screen.getByRole("region", { name: /map/i })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /contacts/i })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /video/i })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /mission log/i })).toBeInTheDocument();
  });

  it("places the map region before the list region in the DOM (map-primary reading order)", () => {
    render(<AppShell {...slots} />);
    const map = screen.getByTestId("slot-map");
    const list = screen.getByTestId("slot-list");
    // map appears earlier in document order than the list rail
    expect(map.compareDocumentPosition(list) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
