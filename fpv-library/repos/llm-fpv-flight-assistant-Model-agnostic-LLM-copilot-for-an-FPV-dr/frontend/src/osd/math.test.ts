import { compassTicks, ladderTicks, headingLabel } from "./math";

test("headingLabel wraps to cardinal", () => {
  expect(headingLabel(0)).toBe("N");
  expect(headingLabel(90)).toBe("E");
  expect(headingLabel(180)).toBe("S");
  expect(headingLabel(270)).toBe("W");
});
test("compassTicks centers on heading within window", () => {
  const t = compassTicks(90, 60, 10); // heading 90, +/-30 window, step 10
  expect(t.some((x) => x.deg === 90 && Math.abs(x.x) < 1e-6)).toBe(true);
});
test("ladderTicks returns ticks around a value", () => {
  const t = ladderTicks(12, 5, 20); // value 12, step 5, span 20
  expect(t.map((x) => x.value)).toContain(10);
  expect(t.map((x) => x.value)).toContain(15);
});
