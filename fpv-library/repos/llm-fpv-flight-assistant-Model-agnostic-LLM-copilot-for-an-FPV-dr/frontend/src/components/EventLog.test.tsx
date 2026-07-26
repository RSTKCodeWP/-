import { render, screen } from "@testing-library/react";
import { EventLog } from "./EventLog";
test("renders entries newest first", () => {
  render(<EventLog events={[{ ts: 1, kind: "result", text: "executed loiter" }, { ts: 2, kind: "control", text: "control: manual" }]} />);
  const items = screen.getAllByRole("listitem");
  expect(items[0]).toHaveTextContent("control: manual");
});
