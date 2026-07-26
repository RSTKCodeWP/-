/**
 * Component tests for INavActionEditors.
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { INavActionEditors } from "@/components/planner/WaypointCommandEditors";
import { INAV_WP_ACTION } from "@/lib/protocol/msp/msp-decoders-inav";
import type { Waypoint } from "@/lib/types";

// Mock lucide-react icons used transitively
vi.mock("lucide-react", () => ({
  ChevronDown: (props: Record<string, unknown>) => <span data-testid="icon-chevron-down" {...props} />,
  ChevronRight: (props: Record<string, unknown>) => <span data-testid="icon-chevron-right" {...props} />,
  Check: (props: Record<string, unknown>) => <span data-testid="icon-check" {...props} />,
  Search: (props: Record<string, unknown>) => <span data-testid="icon-search" {...props} />,
  GripVertical: (props: Record<string, unknown>) => <span {...props} />,
  X: (props: Record<string, unknown>) => <span {...props} />,
}));

const baseWaypoint: Waypoint = {
  id: "wp-1",
  lat: 12.9716,
  lon: 77.5946,
  alt: 50,
  inavAction: INAV_WP_ACTION.WAYPOINT,
};

const noop = () => {};
const baseProps = {
  waypoint: baseWaypoint,
  localParam1: "",
  localParam2: "",
  localParam3: "",
  localHoldTime: "",
  setLocalParam1: noop,
  setLocalParam2: noop,
  setLocalParam3: noop,
  setLocalHoldTime: noop,
  commitField: noop as (field: keyof Waypoint, value: string) => void,
  onUpdate: noop as (update: Partial<Waypoint>) => void,
};

describe("INavActionEditors", () => {
  it("shows speed input for WAYPOINT action", () => {
    render(<INavActionEditors action={INAV_WP_ACTION.WAYPOINT} {...baseProps} />);
    expect(screen.getByLabelText(/Speed/i)).toBeTruthy();
  });

  it("shows hold-time input for POSHOLD_TIME action", () => {
    render(<INavActionEditors action={INAV_WP_ACTION.POSHOLD_TIME} {...baseProps} />);
    expect(screen.getByLabelText(/Hold time/i)).toBeTruthy();
  });

  it("shows target and repeat inputs for JUMP action", () => {
    render(<INavActionEditors action={INAV_WP_ACTION.JUMP} {...baseProps} />);
    expect(screen.getByLabelText(/Target WP/i)).toBeTruthy();
    expect(screen.getByLabelText(/Repeat/i)).toBeTruthy();
  });

  it("shows heading input for SET_HEAD action", () => {
    render(<INavActionEditors action={INAV_WP_ACTION.SET_HEAD} {...baseProps} />);
    expect(screen.getByLabelText(/Heading/i)).toBeTruthy();
  });

  it("shows descriptive hint for POSHOLD_UNLIM action", () => {
    render(<INavActionEditors action={INAV_WP_ACTION.POSHOLD_UNLIM} {...baseProps} />);
    expect(screen.getByText(/Loiters at this position indefinitely/i)).toBeTruthy();
  });
});
