import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Placeholder } from "./Placeholder";

/* Designed empty/loading states, not blank panels or bare spinners (anti-slop #7). */

describe("Placeholder", () => {
  it("renders a labelled, intentional empty state", () => {
    render(<Placeholder label="No contacts yet" hint="Replaying canned mission…" />);
    expect(screen.getByText("No contacts yet")).toBeInTheDocument();
    expect(screen.getByText("Replaying canned mission…")).toBeInTheDocument();
  });

  it("works with just a label", () => {
    render(<Placeholder label="Connecting to service" />);
    expect(screen.getByText("Connecting to service")).toBeInTheDocument();
  });
});
