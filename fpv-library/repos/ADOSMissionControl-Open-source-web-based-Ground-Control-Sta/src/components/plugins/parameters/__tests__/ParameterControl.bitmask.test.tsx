/**
 * @module plugins/parameters/ParameterControl.bitmask.test
 * @description The bitmask widget renders a Set Bitmask trigger + the shared
 * editor and commits an integer value.
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, values?: Record<string, unknown>) =>
    values ? `${key}(${JSON.stringify(values)})` : key,
}));

import { ParameterControl } from "../ParameterControl";
import type { ParsedParameterContribution } from "@/lib/plugins/parameters/parse";

function bitmaskParam(): ParsedParameterContribution {
  return {
    key: "flags",
    schema: { type: "integer" },
    binding: "plugin.config",
    ui: {
      label: "Flags",
      widget: "bitmask",
      bits: [
        { bit: 0, label: "Alpha" },
        { bit: 1, label: "Bravo" },
        { bit: 2, label: "Charlie" },
      ],
    },
  };
}

describe("ParameterControl — bitmask widget", () => {
  it("renders a decoded trigger and commits an integer on Apply", () => {
    const onCommit = vi.fn();
    render(<ParameterControl param={bitmaskParam()} value={5} onCommit={onCommit} />);
    // Trigger shows the decoded summary (bits 0 + 2 set).
    expect(screen.getByText("Alpha, Charlie (5)")).toBeInTheDocument();
    // Open the editor, set bit 1, apply.
    fireEvent.click(screen.getByText("Alpha, Charlie (5)"));
    const boxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    expect(boxes).toHaveLength(3);
    fireEvent.click(boxes[1]); // 5 -> 7
    fireEvent.click(screen.getByText("apply"));
    expect(onCommit).toHaveBeenCalledWith(7);
  });
});
