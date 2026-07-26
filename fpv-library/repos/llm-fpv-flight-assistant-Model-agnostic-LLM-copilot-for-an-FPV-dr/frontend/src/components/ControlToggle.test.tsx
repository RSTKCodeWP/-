import { render, screen, fireEvent } from "@testing-library/react";
import { ControlToggle } from "./ControlToggle";
test("shows TAKE CONTROL in assistant, calls onTake", () => {
  const onTake = vi.fn();
  render(<ControlToggle control="assistant" onTake={onTake} onRelease={() => {}} />);
  fireEvent.click(screen.getByRole("button"));
  expect(onTake).toHaveBeenCalled();
});
test("shows RELEASE in manual, calls onRelease", () => {
  const onRelease = vi.fn();
  render(<ControlToggle control="manual" onTake={() => {}} onRelease={onRelease} />);
  fireEvent.click(screen.getByRole("button"));
  expect(onRelease).toHaveBeenCalled();
});
