import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConfidenceBar } from "./ConfidenceBar";

/* Confidence as a pre-attentive micro-bar with banded fill (DESIGN-SYSTEM §5.2): two raw
 * decimals side by side aren't scannable; the bar is. The exact value lives in the panel.
 * Bar still exposes the value to assistive tech (never-hidden trust field, §6.8). */

describe("ConfidenceBar", () => {
  it("renders an accessible meter carrying the numeric value", () => {
    render(<ConfidenceBar value={0.71} label="localization confidence" />);
    const meter = screen.getByRole("meter", { name: /localization confidence/i });
    expect(meter).toHaveAttribute("aria-valuenow", "0.71");
  });

  it("fill width scales with the value", () => {
    render(<ConfidenceBar value={0.5} label="x" />);
    const fill = screen.getByTestId("conf-fill");
    expect(fill.style.width).toBe("50%");
  });

  it("bands low/med/high by color token", () => {
    const { rerender } = render(<ConfidenceBar value={0.2} label="x" />);
    expect(screen.getByTestId("conf-fill").className).toContain("bg-st-caution"); // low
    rerender(<ConfidenceBar value={0.55} label="x" />);
    expect(screen.getByTestId("conf-fill").className).toContain("bg-st-info"); // med
    rerender(<ConfidenceBar value={0.85} label="x" />);
    expect(screen.getByTestId("conf-fill").className).toContain("bg-st-nominal"); // high
  });

  it("renders a no-data dash when the value is null (e.g. CUE_ONLY localization)", () => {
    render(<ConfidenceBar value={null} label="localization confidence" />);
    expect(screen.getByTestId("conf-nodata")).toHaveTextContent("—");
  });
});
