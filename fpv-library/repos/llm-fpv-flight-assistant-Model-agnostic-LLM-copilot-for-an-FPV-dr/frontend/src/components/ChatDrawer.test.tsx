import { render, screen, fireEvent } from "@testing-library/react";
import { ChatDrawer } from "./ChatDrawer";
const base = { chat: { messages: [{ role: "user", reply: "go" }, { role: "assistant", reply: "Holding", thinking: "reasoning" }], streaming: false } as any,
  proposal: null, onChat: () => {}, onConfirm: () => {}, onCancel: () => {} };
test("renders user + assistant bubbles", () => {
  render(<ChatDrawer {...base} />);
  expect(screen.getByText("go")).toBeInTheDocument();
  expect(screen.getByText("Holding")).toBeInTheDocument();
});
test("shows proposal confirm/cancel", () => {
  const onConfirm = vi.fn();
  render(<ChatDrawer {...base} proposal={{ command: { verb: "loiter" }, say: "ok" }} onConfirm={onConfirm} />);
  fireEvent.click(screen.getByText(/Confirm/));
  expect(onConfirm).toHaveBeenCalled();
});
test("shows thinking indicator while streaming", () => {
  render(<ChatDrawer {...base} chat={{ messages: base.chat.messages, streaming: true } as any} />);
  expect(screen.getByText(/thinking/i)).toBeInTheDocument();
});
