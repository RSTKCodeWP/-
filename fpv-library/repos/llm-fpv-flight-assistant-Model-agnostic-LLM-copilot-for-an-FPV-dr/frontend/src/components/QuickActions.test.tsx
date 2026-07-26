import { render, screen, fireEvent } from "@testing-library/react";
import { QuickActions } from "./QuickActions";
test("takeoff issues quick verb with alt", () => {
  const quick = vi.fn();
  render(<QuickActions quick={quick} />);
  fireEvent.click(screen.getByText(/Takeoff/));
  expect(quick).toHaveBeenCalledWith("arm_takeoff", expect.objectContaining({ alt: expect.any(Number) }));
});
test("RTL issues return_to_launch", () => {
  const quick = vi.fn();
  render(<QuickActions quick={quick} />);
  fireEvent.click(screen.getByText(/RTL/));
  expect(quick).toHaveBeenCalledWith("return_to_launch", {});
});
