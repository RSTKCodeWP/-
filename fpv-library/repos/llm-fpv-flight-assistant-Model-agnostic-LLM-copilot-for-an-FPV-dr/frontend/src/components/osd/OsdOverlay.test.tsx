import { render } from "@testing-library/react";
import { OsdOverlay } from "./OsdOverlay";
test("renders without telemetry", () => {
  const { container } = render(<OsdOverlay t={null} />);
  expect(container).toBeTruthy();
});
test("renders alt/speed when telemetry present", () => {
  const t: any = { alt_m: 12.3, speed_ms: 3.4, roll: 5, pitch: -3, yaw: 90, battery_pct: 0.8, gps_ok: true, ekf_ok: true, flight_mode: "HOLD", armed: true, lat: 0, lon: 0 };
  const { getByText } = render(<OsdOverlay t={t} />);
  expect(getByText("12.3")).toBeTruthy();   // alt readout (unambiguous exact match)
  expect(getByText("3.4")).toBeTruthy();    // speed readout
});
