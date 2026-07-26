import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DocsPanel } from "./DocsPanel";
import { DOC_SECTIONS, DOC_TOOLS } from "./docsContent";

/* Phase 7 Task 7.6 - the in-app docs panel renders the single shared docs source (logo, the four
 * metric families with real figures, the versioned tool list, the honesty disclosures) and closes
 * cleanly. The Playwright gate (tests/docs.spec.ts) proves it renders in the real web build across
 * surfaces; this is the fast unit guard on content + structure. */

afterEach(cleanup);

describe("DocsPanel", () => {
  it("renders the logo, at least one metric figure, and the tool list", () => {
    render(<DocsPanel onClose={() => {}} />);
    expect(screen.getByTestId("docs-logo")).toBeInTheDocument();
    expect(screen.getAllByTestId("docs-figure").length).toBeGreaterThan(0);
    const tools = screen.getByTestId("docs-tools");
    expect(within(tools).getByText(/YOLO11/i)).toBeInTheDocument();
    // The shipped 960 resolution appears in the section tables, not the tool list.
    expect(screen.getByTestId("docs-panel").textContent).toContain("960");
  });

  it("shows every tool with its locked version", () => {
    render(<DocsPanel onClose={() => {}} />);
    const tools = screen.getByTestId("docs-tools");
    for (const t of DOC_TOOLS) {
      expect(within(tools).getByText(t.version)).toBeInTheDocument();
    }
  });

  it("renders one figure per declared figure across all sections", () => {
    render(<DocsPanel onClose={() => {}} />);
    const declared = DOC_SECTIONS.reduce((n, s) => n + (s.figures?.length ?? 0), 0);
    expect(screen.getAllByTestId("docs-figure")).toHaveLength(declared);
  });

  it("carries the sim and dev-floor honesty disclosures in-app", () => {
    render(<DocsPanel onClose={() => {}} />);
    const panel = screen.getByTestId("docs-panel");
    expect(panel.textContent).toMatch(/sim/i);
    expect(panel.textContent).toMatch(/dev.?floor/i);
  });

  it("calls onClose from the close button", () => {
    const onClose = vi.fn();
    render(<DocsPanel onClose={onClose} />);
    fireEvent.click(screen.getByTestId("docs-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
