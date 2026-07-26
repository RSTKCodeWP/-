import { assertAlmostEquals, assertEquals } from "https://deno.land/std@0.208.0/assert/mod.ts";
import {
  calculateThrottle,
  normalizeLimitPercent,
  normalizeLimitType,
} from "../../rate-profile/src/rate-calculator.js";

Deno.test("calculateThrottle - limit type OFF leaves output unchanged", () => {
  const base = calculateThrottle(1.0, 50, 0);
  assertAlmostEquals(calculateThrottle(1.0, 50, 0, "OFF", 60), base, 1e-9);
});

Deno.test("calculateThrottle - SCALE multiplies output by percent", () => {
  const base = calculateThrottle(1.0, 50, 0);
  assertAlmostEquals(
    calculateThrottle(1.0, 50, 0, "SCALE", 80),
    base * 0.8,
    1e-9,
  );
});

Deno.test("calculateThrottle - SCALE at mid stick scales proportionally", () => {
  const base = calculateThrottle(0.5, 50, 0);
  assertAlmostEquals(
    calculateThrottle(0.5, 50, 0, "SCALE", 50),
    base * 0.5,
    1e-9,
  );
});

Deno.test("calculateThrottle - CLIP caps output at percent ceiling", () => {
  assertAlmostEquals(
    calculateThrottle(1.0, 50, 0, "CLIP", 70),
    0.7,
    1e-9,
  );
});

Deno.test("calculateThrottle - CLIP leaves values below ceiling untouched", () => {
  // base at input 0.2 is well below 0.7 ceiling
  const base = calculateThrottle(0.2, 50, 0);
  assertAlmostEquals(
    calculateThrottle(0.2, 50, 0, "CLIP", 70),
    base,
    1e-9,
  );
});

Deno.test("calculateThrottle - 100% limit equals OFF for both modes", () => {
  const base = calculateThrottle(1.0, 50, 0);
  assertEquals(calculateThrottle(1.0, 50, 0, "SCALE", 100), base);
  assertEquals(calculateThrottle(1.0, 50, 0, "CLIP", 100), base);
});

Deno.test("calculateThrottle - unknown limit type behaves as OFF", () => {
  const base = calculateThrottle(0.8, 50, 0);
  assertAlmostEquals(
    calculateThrottle(0.8, 50, 0, "BOGUS", 50),
    base,
    1e-9,
  );
});

Deno.test("calculateThrottle - lowercase limit type is normalized", () => {
  const base = calculateThrottle(1.0, 50, 0);
  assertAlmostEquals(
    calculateThrottle(1.0, 50, 0, "scale", 50),
    base * 0.5,
    1e-9,
  );
});

Deno.test("calculateThrottle - NaN limit percent does not poison output", () => {
  const base = calculateThrottle(1.0, 50, 0);
  assertAlmostEquals(
    calculateThrottle(1.0, 50, 0, "SCALE", NaN),
    base,
    1e-9,
  );
  assertAlmostEquals(
    calculateThrottle(1.0, 50, 0, "CLIP", NaN),
    base,
    1e-9,
  );
});

Deno.test("calculateThrottle - undefined limit type treated as OFF", () => {
  const base = calculateThrottle(0.8, 50, 0);
  assertAlmostEquals(
    calculateThrottle(0.8, 50, 0, undefined, 50),
    base,
    1e-9,
  );
});

Deno.test("normalizeLimitType - accepts canonical strings", () => {
  assertEquals(normalizeLimitType("OFF"), "OFF");
  assertEquals(normalizeLimitType("SCALE"), "SCALE");
  assertEquals(normalizeLimitType("CLIP"), "CLIP");
});

Deno.test("normalizeLimitType - case-insensitive and trims whitespace", () => {
  assertEquals(normalizeLimitType("scale"), "SCALE");
  assertEquals(normalizeLimitType("  clip  "), "CLIP");
});

Deno.test("normalizeLimitType - falls back to OFF for unknown/missing", () => {
  assertEquals(normalizeLimitType("bogus"), "OFF");
  assertEquals(normalizeLimitType(undefined), "OFF");
  assertEquals(normalizeLimitType(null), "OFF");
  assertEquals(normalizeLimitType(""), "OFF");
});

Deno.test("normalizeLimitPercent - keeps valid numbers in range", () => {
  assertEquals(normalizeLimitPercent(25), 25);
  assertEquals(normalizeLimitPercent(80), 80);
  assertEquals(normalizeLimitPercent(100), 100);
});

Deno.test("normalizeLimitPercent - clamps out-of-range to Betaflight 25..100", () => {
  assertEquals(normalizeLimitPercent(-5), 25);
  assertEquals(normalizeLimitPercent(0), 25);
  assertEquals(normalizeLimitPercent(10), 25);
  assertEquals(normalizeLimitPercent(150), 100);
});

Deno.test("normalizeLimitPercent - non-finite values default to 100", () => {
  assertEquals(normalizeLimitPercent(NaN), 100);
  assertEquals(normalizeLimitPercent(Infinity), 100);
  assertEquals(normalizeLimitPercent(undefined), 100);
  assertEquals(normalizeLimitPercent("abc"), 100);
});

Deno.test("normalizeLimitPercent - coerces numeric strings", () => {
  assertEquals(normalizeLimitPercent("70"), 70);
});
