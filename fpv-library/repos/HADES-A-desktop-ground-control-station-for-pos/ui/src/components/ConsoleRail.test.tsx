import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { useNavStore } from "../store/nav";
import { ConsoleRail } from "./ConsoleRail";

/* The console mode-switcher rail (DESIGN-SYSTEM §11.1). The four instrument modes, the active
 * one marked, and clicking switches the global nav store (the spine that drives App's page). */

describe("ConsoleRail", () => {
  beforeEach(() => useNavStore.getState().reset());

  it("renders all four console modes", () => {
    render(<ConsoleRail />);
    for (const m of ["ops", "review", "map", "set"]) {
      expect(screen.getByTestId(`nav-${m}`)).toBeInTheDocument();
    }
  });

  it("marks OPS as the current mode by default", () => {
    render(<ConsoleRail />);
    expect(screen.getByTestId("nav-ops")).toHaveAttribute("aria-current", "page");
    expect(screen.getByTestId("nav-review")).not.toHaveAttribute("aria-current");
  });

  it("clicking a mode switches the global nav store", async () => {
    render(<ConsoleRail />);
    await userEvent.click(screen.getByTestId("nav-map"));
    expect(useNavStore.getState().mode).toBe("map");
    expect(screen.getByTestId("nav-map")).toHaveAttribute("aria-current", "page");
  });
});
