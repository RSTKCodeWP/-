import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { useContactStore } from "../store/contacts";
import { useProvenanceStore } from "../store/provenance";
import { useSystemStore } from "../store/system";
import { VideoPanel } from "./VideoPanel";

describe("VideoPanel", () => {
  beforeEach(() => {
    useContactStore.getState().reset();
    useSystemStore.getState().reset();
    useProvenanceStore.getState().setProvenance(null);
  });

  it("renders a canvas for painting frames", () => {
    render(<VideoPanel />);
    expect(screen.getByTestId("video-canvas")).toBeInTheDocument();
  });

  it("renders the transport controls (rewind, pause, snapshot, manual)", () => {
    render(<VideoPanel />);
    expect(screen.getByRole("button", { name: /rewind/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /pause/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /snapshot/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /manual/i })).toBeInTheDocument();
  });

  it("shows a loud LINK LOST banner when the link is down (frozen never looks live)", () => {
    useSystemStore.getState().setLink(false);
    render(<VideoPanel />);
    expect(screen.getByTestId("link-lost-banner")).toBeInTheDocument();
    expect(screen.getByTestId("link-lost-banner")).toHaveTextContent(/link lost/i);
  });

  it("hides the LINK LOST banner when the link is up", () => {
    render(<VideoPanel />);
    expect(screen.queryByTestId("link-lost-banner")).not.toBeInTheDocument();
  });

  it("manual contact creation adds a contact (the AI-miss backstop, recall-first)", async () => {
    render(<VideoPanel />);
    expect(useContactStore.getState().contacts.size).toBe(0);
    await userEvent.click(screen.getByRole("button", { name: /manual/i }));
    expect(useContactStore.getState().contacts.size).toBe(1);
    // a manually-created contact is honest: CUE_ONLY with no fix (operator marks, doesn't localize)
    const c = [...useContactStore.getState().contacts.values()][0];
    expect(c.actionability_class).toBe("CUE_ONLY");
    expect(c.lat).toBeNull();
  });

  it("shows a designed empty state before any frame arrives", () => {
    render(<VideoPanel />);
    expect(screen.getByText(/no video|awaiting|connecting/i)).toBeInTheDocument();
  });

  it("labels the feed as a SYNTHETIC demo feed in demo mode (never poses a synthetic frame as live)", () => {
    // Demo mode = provenance set (mirrors the demo banner). The baked frame is a near-black
    // synthetic image; an honest UI names it, so a dark frame never reads as a broken/black void.
    useProvenanceStore.getState().setProvenance({
      median_error_m: 1.1,
      note: "synthetic scene, real pipeline",
    } as never);
    render(<VideoPanel />);
    expect(screen.getByTestId("video-demo-badge")).toBeInTheDocument();
    expect(screen.getByTestId("video-demo-badge")).toHaveTextContent(/synthetic|demo/i);
    // and it must NOT show the live "FRESH" indicator in demo mode
    expect(screen.queryByTestId("fresh-indicator")).not.toBeInTheDocument();
  });

  it("shows the live FRESH indicator when NOT in demo mode", () => {
    render(<VideoPanel />);
    expect(screen.queryByTestId("video-demo-badge")).not.toBeInTheDocument();
  });
});
