import {
  assert,
  assertAlmostEquals,
  assertEquals,
} from "https://deno.land/std@0.208.0/assert/mod.ts";
import {
  AIR_DENSITY,
  airDensityAtAltitude,
  analyze,
  discLoading,
  hoverThrottlePercent,
  loadedRpm,
  maxRpm,
  parseMotorSize,
  pitchSpeedKmh,
  recommendAuw,
  recommendCellCount,
  recommendKv,
  recommendMotorSizes,
  recommendPitch,
  recommendPropDiameter,
  staticThrustGrams,
  statorVolume,
  thrustToWeight,
  tipSpeedMs,
} from "../../prop-motor-sizer/src/sizer-calculator.js";

// ---------------------------------------------------------------------------
// Motor size parsing
// ---------------------------------------------------------------------------

Deno.test("parseMotorSize - standard four-digit size", () => {
  assertEquals(parseMotorSize("2207"), { statorDiameter: 22, statorHeight: 7 });
});

Deno.test("parseMotorSize - leading-zero whoop size", () => {
  assertEquals(parseMotorSize("0802"), { statorDiameter: 8, statorHeight: 2 });
});

Deno.test("parseMotorSize - decimal stator height", () => {
  assertEquals(parseMotorSize("2806.5"), { statorDiameter: 28, statorHeight: 6.5 });
});

Deno.test("parseMotorSize - garbage returns null", () => {
  assertEquals(parseMotorSize("not a motor"), null);
  assertEquals(parseMotorSize(""), null);
  assertEquals(parseMotorSize(null), null);
});

Deno.test("statorVolume - cylinder volume in mm³", () => {
  // 2207: π × 11² × 7
  assertAlmostEquals(
    statorVolume({ statorDiameter: 22, statorHeight: 7 }),
    Math.PI * 11 * 11 * 7,
    0.1,
  );
});

// ---------------------------------------------------------------------------
// RPM and speeds
// ---------------------------------------------------------------------------

Deno.test("maxRpm - KV times voltage", () => {
  assertEquals(maxRpm(1800, 25.2), 45360);
});

Deno.test("loadedRpm - default load factor is 75% of unloaded", () => {
  assertAlmostEquals(loadedRpm(1800, 25.2), 34020, 1e-6);
});

Deno.test("tipSpeedMs - circumference times revs per second", () => {
  // 5" prop at 34020 RPM: π × (5 × 0.0254) × 34020/60
  assertAlmostEquals(tipSpeedMs(5, 34020), Math.PI * 5 * 0.0254 * 567, 1e-6);
});

Deno.test("pitchSpeedKmh - pitch advance per rev", () => {
  // 4.5" pitch at 34020 RPM: 4.5 × 0.0254 m/rev × 567 rev/s × 3.6
  assertAlmostEquals(pitchSpeedKmh(4.5, 34020), 4.5 * 0.0254 * 567 * 3.6, 1e-6);
});

// ---------------------------------------------------------------------------
// Static thrust
// ---------------------------------------------------------------------------

Deno.test("staticThrustGrams - 5-inch freestyle setup lands in plausible range", () => {
  // 5x4.5 tri-blade at ~34k loaded RPM (2207 1800KV on 6S): real-world
  // thrust-stand numbers for this class are roughly 1.2-1.9 kg per motor.
  const t = staticThrustGrams(5, 4.5, 34020, 3);
  assert(t > 1100 && t < 1900, `thrust ${t}g outside plausible range`);
});

Deno.test("staticThrustGrams - scales with RPM squared", () => {
  const low = staticThrustGrams(5, 4.5, 20000, 2);
  const high = staticThrustGrams(5, 4.5, 40000, 2);
  assertAlmostEquals(high / low, 4, 1e-9);
});

Deno.test("staticThrustGrams - more blades produce more thrust at same RPM", () => {
  const two = staticThrustGrams(5, 4.5, 30000, 2);
  const three = staticThrustGrams(5, 4.5, 30000, 3);
  const four = staticThrustGrams(5, 4.5, 30000, 4);
  assert(three > two);
  assert(four > three);
  // Diminishing returns: each extra blade adds less than the previous one
  assert(four - three < three - two);
});

// ---------------------------------------------------------------------------
// Weight-relative metrics
// ---------------------------------------------------------------------------

Deno.test("thrustToWeight - simple ratio", () => {
  assertEquals(thrustToWeight(6000, 600), 10);
});

Deno.test("hoverThrottlePercent - thrust proportional to throttle squared", () => {
  // TWR 9 → hover at 1/9 max thrust → sqrt(1/9) = 33.3% throttle
  assertAlmostEquals(hoverThrottlePercent(9), 100 / 3, 0.01);
});

Deno.test("discLoading - grams per cm² of disc area", () => {
  // 650g on four 5" discs: 650 / (4 × π × 6.35²)
  assertAlmostEquals(discLoading(650, 5, 4), 650 / (4 * Math.PI * 6.35 * 6.35), 1e-6);
});

// ---------------------------------------------------------------------------
// Recommendations - KV / cells
// ---------------------------------------------------------------------------

Deno.test("recommendKv - 5-inch on 6S centers near 1800", () => {
  const r = recommendKv(5, 25.2, "freestyle");
  assert(r.ideal > 1600 && r.ideal < 2000, `ideal ${r.ideal}`);
  assert(r.min < 1800 && r.max > 1800);
});

Deno.test("recommendKv - 5-inch on 4S centers near 2600", () => {
  const r = recommendKv(5, 16.8, "freestyle");
  assert(r.ideal > 2400 && r.ideal < 2900, `ideal ${r.ideal}`);
});

Deno.test("recommendKv - 7-inch on 6S centers near 1300-1500", () => {
  const r = recommendKv(7, 25.2, "freestyle");
  assert(r.ideal > 1200 && r.ideal < 1550, `ideal ${r.ideal}`);
});

Deno.test("recommendKv - tiny whoop on 1S lands in the tens of thousands", () => {
  const r = recommendKv(1.2, 4.2, "freestyle");
  assert(r.ideal > 19000 && r.ideal < 28000, `ideal ${r.ideal}`);
});

Deno.test("recommendCellCount - 5-inch 1800KV wants 6S", () => {
  assertEquals(recommendCellCount(5, 1800, "freestyle").ideal, 6);
});

Deno.test("recommendCellCount - 5-inch 2600KV wants 4S", () => {
  assertEquals(recommendCellCount(5, 2600, "freestyle").ideal, 4);
});

Deno.test("recommendCellCount - 7-inch 1300KV wants 6S", () => {
  assertEquals(recommendCellCount(7, 1300, "freestyle").ideal, 6);
});

// ---------------------------------------------------------------------------
// Recommendations - motor size / prop / pitch / AUW
// ---------------------------------------------------------------------------

Deno.test("recommendMotorSizes - 5-inch includes the classic 22xx/23xx stators", () => {
  const { sizes } = recommendMotorSizes(5);
  assert(sizes.includes("2207"), `got ${sizes}`);
  assert(sizes.includes("2306"), `got ${sizes}`);
  assert(!sizes.includes("1404"));
  assert(!sizes.includes("0802"));
});

Deno.test("recommendMotorSizes - 3-inch includes 14xx stators", () => {
  const { sizes } = recommendMotorSizes(3);
  assert(sizes.includes("1404"), `got ${sizes}`);
  assert(!sizes.includes("2207"));
});

Deno.test("recommendMotorSizes - tiny whoop includes 0802", () => {
  const { sizes } = recommendMotorSizes(1.2);
  assert(sizes.includes("0802"), `got ${sizes}`);
});

Deno.test("recommendPropDiameter - 2207 centers on the 5-inch class", () => {
  const r = recommendPropDiameter("2207");
  assert(r.min < 5 && r.max > 5, `range ${r.min}-${r.max}`);
  assert(r.min > 3.5 && r.max < 7.5, `range ${r.min}-${r.max}`);
});

Deno.test("recommendPropDiameter - invalid motor size returns null", () => {
  assertEquals(recommendPropDiameter("nope"), null);
});

Deno.test("recommendPitch - freestyle 5-inch covers common 4.3-4.5 pitches", () => {
  const r = recommendPitch(5, "freestyle");
  assert(r.min <= 4.3 && r.max >= 4.5, `range ${r.min}-${r.max}`);
});

Deno.test("recommendPitch - cinematic runs lower pitch than racing", () => {
  const cine = recommendPitch(5, "cinematic");
  const race = recommendPitch(5, "racing");
  assert(cine.max < race.max);
});

Deno.test("recommendAuw - freestyle band around a 5-inch 6S build includes 650g", () => {
  // ~6kg total static thrust is typical for 2207 1800KV 6S on 5x4.5x3
  const r = recommendAuw(6000, "freestyle");
  assert(r.min < 650 && r.max > 650, `range ${r.min}-${r.max}`);
});

// ---------------------------------------------------------------------------
// analyze() orchestration
// ---------------------------------------------------------------------------

const FULL_5IN_6S = {
  diameterIn: 5,
  pitchIn: 4.5,
  blades: 3,
  motorSize: "2207",
  kv: 1800,
  cells: 6,
  auwGrams: 650,
  motorCount: 4,
  style: "freestyle",
};

Deno.test("analyze - full 5-inch 6S freestyle build produces sane metrics", () => {
  const { metrics, recommendations, verdicts } = analyze(FULL_5IN_6S);
  assertAlmostEquals(metrics.voltage, 25.2, 1e-9);
  assertAlmostEquals(metrics.loadedRpm, 34020, 1e-6);
  assert(metrics.totalThrustG > 4800 && metrics.totalThrustG < 7600);
  assert(metrics.twr > 7 && metrics.twr < 12, `twr ${metrics.twr}`);
  assert(metrics.hoverThrottlePct > 25 && metrics.hoverThrottlePct < 40);
  assert(metrics.tipMach > 0.5 && metrics.tipMach < 0.8);
  // Per-motor max draw ~25-35A and total ~80-140A are typical for this class
  assert(metrics.maxCurrentPerMotorA > 15 && metrics.maxCurrentPerMotorA < 45);
  assert(metrics.maxCurrentA > 60 && metrics.maxCurrentA < 180);
  // Everything was specified, so nothing to recommend
  assertEquals(Object.keys(recommendations).length, 0);
  assert(verdicts.length > 0);
  assert(verdicts.some((v: { level: string }) => v.level === "good"));
});

Deno.test("analyze - sparse inputs yield recommendations instead of metrics", () => {
  const { metrics, recommendations } = analyze({
    diameterIn: 5,
    cells: 6,
    blades: 3,
    motorCount: 4,
    style: "freestyle",
  });
  assert(recommendations.kv, "expected a KV recommendation");
  assert(recommendations.kv.ideal > 1600 && recommendations.kv.ideal < 2000);
  assert(recommendations.motorSizes.sizes.includes("2306"));
  assert(recommendations.pitch, "expected a pitch recommendation");
  assertEquals(metrics.twr, undefined);
});

Deno.test("analyze - unparseable motor size is treated as unset", () => {
  const { recommendations } = analyze({
    diameterIn: 5,
    motorSize: "abc",
    blades: 3,
    motorCount: 4,
    style: "freestyle",
  });
  assert(recommendations.motorSizes, "expected motor size recommendation");
});

Deno.test("analyze - grossly overloaded build gets a 'bad' verdict", () => {
  const { verdicts } = analyze({ ...FULL_5IN_6S, auwGrams: 8000 });
  assert(verdicts.some((v: { level: string }) => v.level === "bad"));
});

Deno.test("analyze - zero or invalid motor count falls back to a quad", () => {
  const base = analyze(FULL_5IN_6S).metrics;
  for (const motorCount of [0, -2, NaN]) {
    const m = analyze({ ...FULL_5IN_6S, motorCount }).metrics;
    assertAlmostEquals(m.totalThrustG, base.totalThrustG, 1e-9);
    assertAlmostEquals(m.discLoadingGCm2, base.discLoadingGCm2, 1e-9);
    assert(Number.isFinite(m.maxCurrentPerMotorA), `per-motor current for count ${motorCount}`);
    assert(Number.isFinite(m.hoverCurrentA), `hover current for count ${motorCount}`);
  }
});

Deno.test("analyze - empty input does not throw", () => {
  const { metrics, recommendations, verdicts } = analyze({});
  assertEquals(Object.keys(metrics).length, 0);
  assertEquals(Object.keys(recommendations).length, 0);
  assertEquals(verdicts.length, 0);
});

// ---------------------------------------------------------------------------
// Advanced mode - altitude / air density
// ---------------------------------------------------------------------------

Deno.test("airDensityAtAltitude - sea level matches the standard constant", () => {
  assertAlmostEquals(airDensityAtAltitude(0), AIR_DENSITY, 1e-9);
});

Deno.test("airDensityAtAltitude - 2000m is about 18% thinner", () => {
  assertAlmostEquals(airDensityAtAltitude(2000), 1.007, 0.01);
});

Deno.test("airDensityAtAltitude - negative or missing altitude clamps to sea level", () => {
  assertAlmostEquals(airDensityAtAltitude(-100), AIR_DENSITY, 1e-9);
  assertAlmostEquals(airDensityAtAltitude(undefined), AIR_DENSITY, 1e-9);
});

Deno.test("staticThrustGrams - thrust scales linearly with air density", () => {
  const seaLevel = staticThrustGrams(5, 4.5, 30000, 3);
  const thin = staticThrustGrams(5, 4.5, 30000, 3, 1.0);
  assertAlmostEquals(thin / seaLevel, 1.0 / AIR_DENSITY, 1e-9);
});

Deno.test("analyze - altitude derates thrust", () => {
  const seaLevel = analyze(FULL_5IN_6S).metrics;
  const at2000 = analyze({ ...FULL_5IN_6S, altitudeM: 2000 }).metrics;
  const ratio = at2000.totalThrustG / seaLevel.totalThrustG;
  assert(ratio > 0.8 && ratio < 0.84, `ratio ${ratio}`);
});

// ---------------------------------------------------------------------------
// Advanced mode - load factor and voltage basis
// ---------------------------------------------------------------------------

Deno.test("analyze - custom load factor moves loaded RPM", () => {
  const { metrics } = analyze({ ...FULL_5IN_6S, loadFactor: 0.85 });
  assertAlmostEquals(metrics.loadedRpm, 1800 * 25.2 * 0.85, 1e-6);
});

Deno.test("analyze - per-cell voltage changes metrics but not recommendations", () => {
  // Metrics at nominal 3.7V/cell; KV recommendations stay on the full-charge
  // convention so they match how the community quotes KV.
  const { metrics, recommendations } = analyze({
    diameterIn: 5,
    cells: 6,
    blades: 3,
    motorCount: 4,
    style: "freestyle",
    cellVoltage: 3.7,
  });
  assertAlmostEquals(metrics.voltage, 22.2, 1e-9);
  assert(
    recommendations.kv.ideal > 1600 && recommendations.kv.ideal < 2000,
    `ideal ${recommendations.kv.ideal}`,
  );
});

// ---------------------------------------------------------------------------
// Advanced mode - battery capacity and hover endurance
// ---------------------------------------------------------------------------

Deno.test("analyze - battery capacity yields a plausible hover endurance", () => {
  const { metrics } = analyze({ ...FULL_5IN_6S, capacityMah: 1300 });
  assert(
    metrics.hoverFlightTimeMin > 8 && metrics.hoverFlightTimeMin < 25,
    `endurance ${metrics.hoverFlightTimeMin}`,
  );
});

Deno.test("analyze - no capacity means no endurance metric", () => {
  assertEquals(analyze(FULL_5IN_6S).metrics.hoverFlightTimeMin, undefined);
});

// ---------------------------------------------------------------------------
// Advanced mode - thrust-stand calibration
// ---------------------------------------------------------------------------

Deno.test("analyze - measured thrust calibrates the model", () => {
  const { metrics } = analyze({ ...FULL_5IN_6S, measuredThrustG: 1650 });
  assertAlmostEquals(metrics.thrustPerMotorG, 1650, 1e-9);
  assertAlmostEquals(metrics.totalThrustG, 6600, 1e-9);
  assertAlmostEquals(metrics.twr, 6600 / 650, 1e-9);
  assert(
    metrics.calibrationFactor > 1.0 && metrics.calibrationFactor < 1.2,
    `factor ${metrics.calibrationFactor}`,
  );
});

Deno.test("analyze - calibration adds an info verdict", () => {
  const { verdicts } = analyze({ ...FULL_5IN_6S, measuredThrustG: 1650 });
  assert(verdicts.some((v: { text: string }) => v.text.includes("alibrat")));
});
