import { render, screen } from "@testing-library/react";
import { Chip } from "./Chip";
test("renders label and status color", () => {
  render(<Chip label="LINK" status="ok" />);
  expect(screen.getByText("LINK")).toBeInTheDocument();
});
