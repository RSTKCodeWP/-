/**
 * @module fc/parameters/enum-select.test
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, values?: Record<string, unknown>) =>
    values ? `${key}(${JSON.stringify(values)})` : key,
}));

// Stub the portal Select with a native one so option-building + commit are
// deterministic to assert.
vi.mock("@/components/ui/select", () => ({
  Select: ({
    options,
    value,
    onChange,
  }: {
    options: { value: string; label: string }[];
    value: string;
    onChange: (v: string) => void;
  }) => (
    <select data-testid="enum-select" value={value} onChange={(e) => onChange(e.target.value)}>
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  ),
}));

import { EnumSelect } from "../EnumSelect";

const values = new Map<number, string>([
  [0, "Stabilize"],
  [5, "Loiter"],
  [9, "Land"],
]);

describe("EnumSelect", () => {
  it("renders code: label options and commits the chosen numeric value", () => {
    const onChange = vi.fn();
    const onClose = vi.fn();
    render(<EnumSelect values={values} value={5} onChange={onChange} onClose={onClose} />);
    const select = screen.getByTestId("enum-select") as HTMLSelectElement;
    expect(screen.getByText("5: Loiter")).toBeInTheDocument();
    fireEvent.change(select, { target: { value: "9" } });
    expect(onChange).toHaveBeenCalledWith(9);
    expect(onClose).toHaveBeenCalled();
  });

  it("keeps an out-of-enum value selectable as a custom option", () => {
    render(<EnumSelect values={values} value={42} onChange={vi.fn()} />);
    // The custom option label comes from the mocked t() → "customValue({...})".
    expect(screen.getByText(/customValue/)).toBeInTheDocument();
  });

  it("allows typing an arbitrary numeric value via the 123 toggle", () => {
    const onChange = vi.fn();
    const onClose = vi.fn();
    render(<EnumSelect values={values} value={5} onChange={onChange} onClose={onClose} />);
    fireEvent.click(screen.getByText("123"));
    const input = screen.getByRole("textbox") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "17" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(17);
    expect(onClose).toHaveBeenCalled();
  });
});
