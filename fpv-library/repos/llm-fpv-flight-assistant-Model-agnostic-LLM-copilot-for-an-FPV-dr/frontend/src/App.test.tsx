import { render, screen } from "@testing-library/react";

class FakeWS {
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  constructor(_url: string) {}
  send(_d: string) {}
  close() {}
}
beforeAll(() => { (globalThis as any).WebSocket = FakeWS as any; });

// Stub the WebGL fallback so jsdom doesn't try to render Three.js (no ResizeObserver).
vi.mock("./components/FallbackScene", () => ({ FallbackScene: () => <div data-testid="fallback" /> }));

import { App } from "./App";

test("renders the cockpit shell", () => {
  render(<App />);
  expect(screen.getByText("ASSISTANT")).toBeInTheDocument();   // ControlToggle default state
  expect(screen.getByText(/Takeoff/)).toBeInTheDocument();      // QuickActions present
});
