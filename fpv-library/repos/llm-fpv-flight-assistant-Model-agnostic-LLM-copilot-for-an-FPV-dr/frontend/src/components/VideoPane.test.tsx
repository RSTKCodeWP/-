import { render, screen } from "@testing-library/react";
import { VideoPane } from "./VideoPane";

// Stub the WebGL fallback so jsdom doesn't try to render Three.js.
vi.mock("./FallbackScene", () => ({ FallbackScene: () => <div data-testid="fallback" /> }));

test("shows MJPEG image when video is ok", () => {
  render(<VideoPane videoStatus={{ ok: true, url: "http://x/s.mjpg" }} telemetry={null} />);
  const img = screen.getByRole("img") as HTMLImageElement;
  expect(img.src).toContain("http://x/s.mjpg");
});

test("shows the fallback scene when video is not ok", () => {
  render(<VideoPane videoStatus={{ ok: false, url: "http://x/s.mjpg" }} telemetry={null} />);
  expect(screen.getByTestId("fallback")).toBeInTheDocument();
});

test("shows the fallback scene when status is unknown", () => {
  render(<VideoPane videoStatus={null} telemetry={null} />);
  expect(screen.getByTestId("fallback")).toBeInTheDocument();
});
