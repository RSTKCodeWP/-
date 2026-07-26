import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { useClearanceStore } from "../store/clearanceStore";
import { useContactStore } from "../store/contacts";
import { useSelectionStore } from "../store/selection";
import type { ContactRecord } from "../types/wire";
import { ReviewPage } from "./ReviewPage";

/* REVIEW page (UI overhaul §11.2 / Stage 4.2) — the roomy full-page contact manager. It's a
 * different task from the live rail: a wider table + a clearance FILTER (the rail can't filter)
 * + the per-contact detail + the timeline. It reads the SAME global stores, so the selection
 * spine is shared. These assert the manager-specific behavior; the shared row/clearance logic is
 * covered by the ContactList/clearance tests. */

function contact(track_id: number, over: Partial<ContactRecord> = {}): ContactRecord {
  return {
    track_id,
    actionability_class: "PINPOINT",
    detection_conf: 0.9,
    localization_conf: 0.8,
    lat: 30.2,
    lon: -88.5,
    age_frames: 30,
    convergence_state: "STABLE",
    heading_limited: false,
    frame_id: 1,
    r95_m: 10,
    ...over,
  } as ContactRecord;
}

describe("ReviewPage", () => {
  beforeEach(() => {
    useContactStore.getState().reset();
    useClearanceStore.getState().reset();
    useSelectionStore.getState().reset();
    const store = useContactStore.getState();
    store.ingestContact(contact(42));
    store.ingestContact(contact(37, { actionability_class: "SWEEP" }));
    store.ingestContact(contact(19, { actionability_class: "CUE_ONLY", lat: null, lon: null }));
  });

  it("renders a full-page contact table with every seeded contact", () => {
    render(<ReviewPage />);
    const table = screen.getByTestId("review-table");
    expect(within(table).getAllByRole("row").length).toBeGreaterThanOrEqual(3);
  });

  it("filters the table by clearance state (the rail can't do this)", async () => {
    // mark 42 FOUND so a 'FOUND' filter should isolate it
    useClearanceStore.getState().set(42, "FOUND");
    render(<ReviewPage />);

    // initially all three rows present
    expect(screen.getByTestId("review-row-42")).toBeInTheDocument();
    expect(screen.getByTestId("review-row-37")).toBeInTheDocument();

    // filter to FOUND only
    await userEvent.selectOptions(screen.getByTestId("review-filter"), "FOUND");
    expect(screen.getByTestId("review-row-42")).toBeInTheDocument();
    expect(screen.queryByTestId("review-row-37")).not.toBeInTheDocument();
  });

  it("selecting a row drives the shared selection spine and shows the detail", async () => {
    render(<ReviewPage />);
    await userEvent.click(screen.getByTestId("review-row-37"));
    expect(useSelectionStore.getState().selectedId).toBe(37);
    // the detail region reflects the selection
    expect(screen.getByTestId("review-detail")).toHaveAttribute("data-track-id", "37");
  });

  it("shows an empty-detail prompt when nothing is selected", () => {
    render(<ReviewPage />);
    expect(screen.getByTestId("review-detail")).toHaveTextContent(/select a contact/i);
  });
});
