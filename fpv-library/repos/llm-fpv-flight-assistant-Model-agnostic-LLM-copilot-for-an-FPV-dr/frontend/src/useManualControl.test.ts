import { keysToSetpoint } from "./useManualControl";

test("WASD maps to body velocity at cruise speed", () => {
  const sp = keysToSetpoint(new Set(["w"]), 12);
  expect(sp.forward).toBeCloseTo(6);  // half of max without boost
  expect(sp.right).toBe(0);
});
test("shift boosts to max", () => {
  expect(keysToSetpoint(new Set(["w", "shift"]), 12).forward).toBeCloseTo(12);
});
test("d strafes right, q yaws left", () => {
  expect(keysToSetpoint(new Set(["d"]), 12).right).toBeGreaterThan(0);
  expect(keysToSetpoint(new Set(["q"]), 12).yaw_rate).toBeLessThan(0);
});
test("r climbs (down negative)", () => {
  expect(keysToSetpoint(new Set(["r"]), 12).down).toBeLessThan(0);
});
test("no keys = zero", () => {
  const sp = keysToSetpoint(new Set(), 12);
  expect(sp).toEqual({ forward: 0, right: 0, down: 0, yaw_rate: 0 });
});
