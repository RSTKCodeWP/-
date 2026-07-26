/**
 * @module plugins/parameters/ParameterControl.test
 * @description Render + commit tests for the schema-driven parameter control:
 * a number widget clamps to schema bounds before committing, an enum widget
 * renders its options and commits the chosen value, and a boolean widget
 * toggles.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { ParameterControl } from "../ParameterControl";
import type { ParsedParameterContribution } from "@/lib/plugins/parameters/parse";

function numberParam(): ParsedParameterContribution {
  return {
    key: "speed",
    schema: { type: "number", minimum: 0, maximum: 10 },
    binding: "plugin.config",
    ui: { label: "Speed" },
  };
}

function enumParam(): ParsedParameterContribution {
  return {
    key: "mode",
    schema: { type: "string", enum: ["alpha", "bravo", "charlie"] },
    binding: "plugin.config",
    ui: { label: "Mode" },
  };
}

function booleanParam(): ParsedParameterContribution {
  return {
    key: "active",
    schema: { type: "boolean" },
    binding: "plugin.config",
    ui: { label: "Active" },
  };
}

describe("ParameterControl — number widget", () => {
  it("clamps an over-range value to the schema maximum before committing", () => {
    const onCommit = vi.fn();
    render(
      <ParameterControl param={numberParam()} value={5} onCommit={onCommit} />,
    );
    const input = screen.getByRole("spinbutton");
    fireEvent.change(input, { target: { value: "20" } });
    fireEvent.blur(input);
    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith(10);
  });

  it("rejects a non-numeric entry without committing", () => {
    const onCommit = vi.fn();
    render(
      <ParameterControl param={numberParam()} value={5} onCommit={onCommit} />,
    );
    const input = screen.getByRole("spinbutton");
    fireEvent.change(input, { target: { value: "not-a-number" } });
    fireEvent.blur(input);
    expect(onCommit).not.toHaveBeenCalled();
  });
});

describe("ParameterControl — enum widget", () => {
  it("renders the schema options and commits the chosen value", () => {
    const onCommit = vi.fn();
    render(
      <ParameterControl param={enumParam()} value="alpha" onCommit={onCommit} />,
    );
    // Open the custom dropdown, then pick the second option.
    fireEvent.click(screen.getByRole("combobox"));
    fireEvent.click(screen.getByText("bravo"));
    expect(onCommit).toHaveBeenCalledWith("bravo");
  });
});

describe("ParameterControl — boolean widget", () => {
  it("commits the toggled value", () => {
    const onCommit = vi.fn();
    render(
      <ParameterControl
        param={booleanParam()}
        value={false}
        onCommit={onCommit}
      />,
    );
    fireEvent.click(screen.getByRole("switch"));
    expect(onCommit).toHaveBeenCalledWith(true);
  });
});

describe("ParameterControl — model widget", () => {
  it("renders a read-only affordance with no drone context", () => {
    const onCommit = vi.fn();
    const param: ParsedParameterContribution = {
      key: "detector",
      schema: { type: "string" },
      binding: "engine.detector",
      ui: { label: "Detector", widget: "model" },
    };
    // No droneId → the picker has nowhere to write, so the control falls back
    // to a read-only display of the current value.
    render(
      <ParameterControl
        param={param}
        value="yolov8n"
        disabled
        onCommit={onCommit}
      />,
    );
    expect(screen.getByText("yolov8n")).toBeDefined();
    expect(screen.getByText("Detector")).toBeDefined();
    // No interactive control is offered without a drone to write to.
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
