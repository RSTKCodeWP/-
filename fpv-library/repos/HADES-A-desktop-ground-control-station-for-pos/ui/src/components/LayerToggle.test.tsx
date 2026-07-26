import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { useLayerStore } from "../store/layers";
import { LayerToggle } from "./LayerToggle";

describe("LayerToggle", () => {
  beforeEach(() => useLayerStore.getState().reset());

  it("renders a toggle for each context layer", () => {
    render(<LayerToggle />);
    for (const name of [/coverage/i, /track/i, /footprint/i, /uncertainty/i]) {
      expect(screen.getByRole("switch", { name })).toBeInTheDocument();
    }
  });

  it("reflects the store's visibility state (checked by default)", () => {
    render(<LayerToggle />);
    expect(screen.getByRole("switch", { name: /coverage/i })).toHaveAttribute("aria-checked", "true");
  });

  it("clicking a toggle flips that layer in the store", async () => {
    render(<LayerToggle />);
    await userEvent.click(screen.getByRole("switch", { name: /coverage/i }));
    expect(useLayerStore.getState().visible.coverage).toBe(false);
  });
});
