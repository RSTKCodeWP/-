import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { useClearanceStore } from "../store/clearanceStore";
import { useContactStore } from "../store/contacts";
import { useSelectionStore } from "../store/selection";
import { useSystemStore } from "../store/system";
import type { ContactRecord } from "../types/wire";
import { ContactDetailPanel } from "./ContactDetailPanel";

function c(over: Partial<ContactRecord>): ContactRecord {
  return {
    type: "contact",
    frame_id: 0,
    track_id: 42,
    lat: 30.215,
    lon: -88.52,
    r95_m: 18,
    actionability_class: "PINPOINT",
    semi_major_m: 22,
    semi_minor_m: 14,
    orientation_deg: 30,
    priority_tier: "strong",
    convergence_state: "STABLE",
    heading_limited: false,
    aspect_spread_deg: 40,
    detection_conf: 0.94,
    localization_conf: 0.71,
    mc_reject_fraction: 0.02,
    moving_suspected: false,
    age_frames: 90,
    ...over,
  };
}

function seedSelected(rec: ContactRecord) {
  useContactStore.getState().ingestContact(rec);
  useSelectionStore.getState().select(rec.track_id);
}

describe("ContactDetailPanel", () => {
  beforeEach(() => {
    useContactStore.getState().reset();
    useSelectionStore.getState().reset();
    useClearanceStore.getState().reset();
    useSystemStore.getState().reset();
  });

  it("shows a prompt when nothing is selected", () => {
    render(<ContactDetailPanel />);
    expect(screen.getByText(/select a contact/i)).toBeInTheDocument();
  });

  it("shows the track id always (radio-usable)", () => {
    seedSelected(c({ track_id: 42 }));
    render(<ContactDetailPanel />);
    expect(screen.getByTestId("detail-track")).toHaveTextContent("42");
  });

  it("renders BOTH coordinate formats with the datum (grid primary + DDM secondary)", () => {
    seedSelected(c({ track_id: 42 }));
    render(<ContactDetailPanel />);
    expect(screen.getByTestId("coord-grid").textContent).toMatch(/[A-Z]{2} \d+ \d+/); // MGRS
    expect(screen.getByTestId("coord-geographic").textContent).toMatch(/^N30 /); // DDM
    expect(screen.getByTestId("coord-datum")).toHaveTextContent(/HAE|MSL|REL|UNKNOWN/);
  });

  it("a null-fix contact shows NO FIX, never a phantom coordinate", () => {
    seedSelected(c({ track_id: 9, lat: null, lon: null, actionability_class: "CUE_ONLY" }));
    render(<ContactDetailPanel />);
    expect(screen.getByTestId("coord-grid")).toHaveTextContent(/no fix/i);
  });

  it("shows the never-hidden trust fields (both confidences, age, r95, heading-limited)", () => {
    seedSelected(c({ track_id: 42, heading_limited: true }));
    render(<ContactDetailPanel />);
    const panel = screen.getByTestId("contact-detail");
    expect(within(panel).getByText(/det/i)).toBeInTheDocument();
    expect(within(panel).getByText(/loc/i)).toBeInTheDocument();
    expect(within(panel).getByText(/r95/i)).toBeInTheDocument();
    expect(within(panel).getByText(/heading-limited/i)).toBeInTheDocument();
  });

  it("the primary verb advances clearance one click and is reversible (undo)", async () => {
    seedSelected(c({ track_id: 42 }));
    render(<ContactDetailPanel />);
    await userEvent.click(screen.getByRole("button", { name: /dispatch/i }));
    expect(useClearanceStore.getState().get(42)).toBe("ASSIGNED");
    await userEvent.click(screen.getByRole("button", { name: /undo/i }));
    expect(useClearanceStore.getState().get(42)).toBe("NEW");
  });

  it("dispatching snapshots the coordinate (for later delta)", async () => {
    seedSelected(c({ track_id: 42, lat: 30.215, lon: -88.52 }));
    render(<ContactDetailPanel />);
    await userEvent.click(screen.getByRole("button", { name: /dispatch/i }));
    expect(useClearanceStore.getState().dispatchSnapshot.get(42)).toEqual({ lat: 30.215, lon: -88.52 });
  });

  it("the promote→fuse action sends a promote command for the selected track (M6)", async () => {
    const { commandSink } = await import("../ws/commandSink");
    const promoted: number[] = [];
    commandSink.setHandler((id) => promoted.push(id));
    seedSelected(c({ track_id: 42 }));
    render(<ContactDetailPanel />);
    await userEvent.click(screen.getByRole("button", { name: /promote to fuse/i }));
    expect(promoted).toEqual([42]);
    commandSink.setHandler(null);
  });

  it("effective localization confidence collapses when telemetry goes stale (M12)", () => {
    seedSelected(c({ track_id: 42, localization_conf: 0.8 }));
    useSystemStore.getState().setTelemetryAge(8);
    render(<ContactDetailPanel />);
    // the LOC meter reflects the COLLAPSED effective value, and a STALE flag appears
    expect(screen.getByTestId("contact-detail")).toHaveTextContent(/stale/i);
  });
});
