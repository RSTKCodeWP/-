import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { useProvenanceStore } from "../store/provenance";
import { DemoBanner } from "./DemoBanner";

/* Phase 6 Task 6.3 — the demo-mode banner (adversarial demo-craft panel R5). It must be HONEST:
 * state exactly which numbers are real (localizer output) vs scripted (scene/pose), surface the
 * real median error as the "flex", and use the off-ramp VIOLET-SLATE (`--st-stale`) — NOT
 * magenta (a demo is an epistemic caveat, not a system-integrity failure, the P0 color rule). */

beforeEach(() => useProvenanceStore.getState().setProvenance(null));
afterEach(cleanup);

describe("DemoBanner", () => {
  it("renders nothing when there is no provenance (live app / synthetic mock)", () => {
    const { container } = render(<DemoBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("shows the honest caveat + the real median error when a baked mission is replaying", () => {
    useProvenanceStore.getState().setProvenance({
      scene: "synthetic",
      pipeline: "real",
      median_error_m: 1.1,
      note: "Synthetic scene, real pipeline. ...",
    });
    render(<DemoBanner />);
    const banner = screen.getByTestId("demo-banner");
    expect(banner.textContent).toMatch(/DEMO/i);
    expect(banner.textContent).toMatch(/synthetic scene/i);
    expect(banner.textContent).toMatch(/real pipeline/i);
    // the real median error is surfaced (the honesty-as-flex)
    expect(banner.textContent).toMatch(/1\.1\s*m/i);
    // and it states there is no live feed
    expect(banner.textContent).toMatch(/no live feed/i);
  });

  it("uses the off-ramp violet-slate token, never magenta/critical", () => {
    useProvenanceStore.getState().setProvenance({
      scene: "synthetic",
      pipeline: "real",
      median_error_m: 1.1,
      note: "n",
    });
    render(<DemoBanner />);
    const banner = screen.getByTestId("demo-banner");
    const cls = banner.className;
    expect(cls).toMatch(/st-stale/);
    expect(cls).not.toMatch(/st-critical/);
  });

  it("discloses full provenance behind a details toggle", () => {
    useProvenanceStore.getState().setProvenance({
      scene: "synthetic",
      pipeline: "real",
      median_error_m: 1.1,
      note: "Real drone footage with full pose lands in a later release.",
    });
    render(<DemoBanner />);
    expect(screen.queryByText(/later release/i)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /details/i }));
    expect(screen.getByText(/later release/i)).toBeInTheDocument();
  });
});
