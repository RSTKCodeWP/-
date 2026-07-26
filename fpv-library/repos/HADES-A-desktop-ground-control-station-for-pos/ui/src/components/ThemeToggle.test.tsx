import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { useThemeStore } from "../store/theme";
import { ThemeToggle } from "./ThemeToggle";

/* The day/night theme toggle (DESIGN-SYSTEM §2.5). Day is default; Night (the original dark
 * palette) must stay REACHABLE — clicking writes the `data-theme` attribute that the token
 * override keys off, so the whole console flips without a component rewrite. */

describe("ThemeToggle", () => {
  beforeEach(() => {
    document.documentElement.setAttribute("data-theme", "day");
    useThemeStore.setState({ theme: "day" });
  });
  afterEach(() => document.documentElement.setAttribute("data-theme", "day"));

  it("shows DAY active by default", () => {
    render(<ThemeToggle />);
    expect(screen.getByTestId("theme-day")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByTestId("theme-night")).toHaveAttribute("aria-checked", "false");
  });

  it("clicking NIGHT flips the theme + writes the html data-theme attribute (dark is reachable)", async () => {
    render(<ThemeToggle />);
    await userEvent.click(screen.getByTestId("theme-night"));
    expect(useThemeStore.getState().theme).toBe("night");
    expect(document.documentElement.getAttribute("data-theme")).toBe("night");
    expect(screen.getByTestId("theme-night")).toHaveAttribute("aria-checked", "true");
  });

  it("clicking DAY again returns to the light default", async () => {
    useThemeStore.getState().setTheme("night");
    render(<ThemeToggle />);
    await userEvent.click(screen.getByTestId("theme-day"));
    expect(useThemeStore.getState().theme).toBe("day");
    expect(document.documentElement.getAttribute("data-theme")).toBe("day");
  });
});
