import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { useClearanceStore } from "../store/clearanceStore";
import { useContactStore } from "../store/contacts";
import { useSelectionStore } from "../store/selection";
import type { ContactRecord } from "../types/wire";
import { ContactList } from "./ContactList";

function c(over: Partial<ContactRecord>): ContactRecord {
  return {
    type: "contact",
    frame_id: 0,
    track_id: 1,
    lat: 30,
    lon: -88,
    r95_m: 18,
    actionability_class: "SWEEP",
    semi_major_m: 22,
    semi_minor_m: 14,
    orientation_deg: 30,
    priority_tier: "candidate",
    convergence_state: "STABLE",
    heading_limited: false,
    aspect_spread_deg: 40,
    detection_conf: 0.9,
    localization_conf: 0.6,
    mc_reject_fraction: 0,
    moving_suspected: false,
    age_frames: 30,
    ...over,
  };
}

function seed(records: ContactRecord[]) {
  for (const r of records) useContactStore.getState().ingestContact(r);
}

describe("ContactList", () => {
  beforeEach(() => {
    useContactStore.getState().reset();
    useSelectionStore.getState().reset();
    useClearanceStore.getState().reset();
  });

  it("renders all non-negotiable column headers", () => {
    seed([c({ track_id: 1 })]); // headers render with the table, not the empty state
    render(<ContactList />);
    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent);
    const joined = headers.join("|").toLowerCase();
    for (const col of ["trk", "class", "det", "loc", "clr", "age", "conv", "hdg"]) {
      expect(joined).toContain(col);
    }
  });

  it("renders one row per contact with the track id", () => {
    seed([c({ track_id: 42 }), c({ track_id: 7 })]);
    render(<ContactList />);
    expect(screen.getByTestId("row-42")).toBeInTheDocument();
    expect(screen.getByTestId("row-7")).toBeInTheDocument();
  });

  it("shows the two confidences as SEPARATE meters per row", () => {
    seed([c({ track_id: 42, detection_conf: 0.94, localization_conf: 0.71 })]);
    render(<ContactList />);
    const row = screen.getByTestId("row-42");
    expect(within(row).getByRole("meter", { name: /detection/i })).toBeInTheDocument();
    expect(within(row).getByRole("meter", { name: /localization/i })).toBeInTheDocument();
  });

  it("clicking a row commits it as the global selection (row → selection)", async () => {
    seed([c({ track_id: 42 })]);
    render(<ContactList />);
    await userEvent.click(screen.getByTestId("row-42"));
    expect(useSelectionStore.getState().selectedId).toBe(42);
  });

  it("reflects an externally-set selection (selection → row), bidirectional", () => {
    seed([c({ track_id: 42 })]);
    useSelectionStore.getState().select(42);
    render(<ContactList />);
    expect(screen.getByTestId("row-42")).toHaveAttribute("aria-selected", "true");
  });

  it("hovering a row sets the hover preview, not the commit", async () => {
    seed([c({ track_id: 42 })]);
    render(<ContactList />);
    await userEvent.hover(screen.getByTestId("row-42"));
    expect(useSelectionStore.getState().hoveredId).toBe(42);
    expect(useSelectionStore.getState().selectedId).toBeNull();
  });

  it("orders the most actionable contact first by default", () => {
    seed([
      c({ track_id: 1, actionability_class: "CUE_ONLY", priority_tier: "contact" }),
      c({ track_id: 2, actionability_class: "PINPOINT", priority_tier: "strong" }),
    ]);
    render(<ContactList />);
    const rows = screen.getAllByRole("row").filter((r) => r.getAttribute("data-testid")?.startsWith("row-"));
    expect(rows[0].getAttribute("data-testid")).toBe("row-2");
  });

  it("flags heading-limited contacts and marks STABLE vs CONVERGING", () => {
    seed([c({ track_id: 42, heading_limited: true, convergence_state: "CONVERGING" })]);
    render(<ContactList />);
    const row = screen.getByTestId("row-42");
    expect(row).toHaveTextContent(/HL/i); // heading-limited flag
    expect(row).toHaveTextContent(/CONV/i);
  });

  it("shows a designed empty state when there are no contacts", () => {
    render(<ContactList />);
    expect(screen.getByText(/no contacts yet/i)).toBeInTheDocument();
  });

  it("demotes a cleared (FOUND) contact below an active one", () => {
    seed([
      c({ track_id: 1, actionability_class: "SWEEP", priority_tier: "candidate" }),
      c({ track_id: 2, actionability_class: "PINPOINT", priority_tier: "strong" }),
    ]);
    useClearanceStore.getState().set(2, "FOUND");
    render(<ContactList />);
    const rows = screen.getAllByRole("row").filter((r) => r.getAttribute("data-testid")?.startsWith("row-"));
    expect(rows[0].getAttribute("data-testid")).toBe("row-1");
    expect(rows[1].getAttribute("data-testid")).toBe("row-2");
  });
});
