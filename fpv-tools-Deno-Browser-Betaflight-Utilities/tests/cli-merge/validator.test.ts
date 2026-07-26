import { assertEquals } from "https://deno.land/std@0.208.0/assert/mod.ts";
import { extractVersion, validate } from "../../cli-merge/src/validator.js";
import { compareSections, parseCLI } from "../../cli-merge/src/parser.js";

Deno.test("extractVersion - reads semver from Betaflight header line", () => {
  const text =
    `# Betaflight / STM32F745 (S745) 4.4.0 Nov  1 2022 / 01:00:00 (abc) MSP API: 1.45\nbatch start`;
  assertEquals(extractVersion(text), "4.4.0");
});

Deno.test("extractVersion - handles 4.5.x header format", () => {
  const text = `# Betaflight / STM32H743 (SH74) 4.5.1 Apr 30 2024 / 12:34:56 (def)`;
  assertEquals(extractVersion(text), "4.5.1");
});

Deno.test("extractVersion - returns null when no version present", () => {
  assertEquals(extractVersion("batch start\n# feature"), null);
});

Deno.test("extractVersion - returns null on empty input", () => {
  assertEquals(extractVersion(""), null);
});

const DUMP_A = `# Betaflight / STM32F745 (S745) 4.4.0 Nov  1 2022 / 01:00:00 (abc)
# start the command batch
batch start

# master
set gyro_lpf1_static_hz = 0
set gyro_lpf2_static_hz = 500

profile 0

# profile
set dterm_lpf1_dyn_min_hz = 75

# save configuration
save`;

const DUMP_B_NEWER = `# Betaflight / STM32F745 (S745) 4.5.1 Apr 30 2024 / 12:34:56 (def)
batch start

# master
set gyro_lpf1_static_hz = 0
set gyro_lpf2_static_hz = 500
set new_key_added_in_45 = 42

profile 0

# profile
set dterm_lpf1_dyn_min_hz = 80

# save configuration
save`;

function buildContext(a, b) {
  const secA = parseCLI(a);
  const secB = parseCLI(b);
  return {
    sections: compareSections(secA, secB),
    versionA: extractVersion(a),
    versionB: extractVersion(b),
  };
}

Deno.test("validate - flags keys introduced only by B when target is A", () => {
  const ctx = buildContext(DUMP_A, DUMP_B_NEWER);
  const merged = `# master\nset gyro_lpf1_static_hz = 0\nset new_key_added_in_45 = 42\n\nsave`;
  const findings = validate({ mergedText: merged, ...ctx });
  const keyDrift = findings.find((f) => f.category === "unknown-key");
  assertEquals(keyDrift !== undefined, true);
  assertEquals(keyDrift.key, "new_key_added_in_45");
  assertEquals(keyDrift.severity, "warning");
});

Deno.test("validate - does not flag shared keys as unknown", () => {
  const ctx = buildContext(DUMP_A, DUMP_B_NEWER);
  const merged = `# master\nset gyro_lpf1_static_hz = 0\n\nsave`;
  const findings = validate({ mergedText: merged, ...ctx });
  assertEquals(findings.some((f) => f.category === "unknown-key"), false);
});

Deno.test("validate - version mismatch produces an info finding", () => {
  const ctx = buildContext(DUMP_A, DUMP_B_NEWER);
  const findings = validate({ mergedText: "save", ...ctx });
  const mismatch = findings.find((f) => f.category === "version-mismatch");
  assertEquals(mismatch !== undefined, true);
  assertEquals(mismatch.severity, "info");
});

Deno.test("validate - matching versions produce no mismatch finding", () => {
  const ctx = buildContext(DUMP_A, DUMP_A);
  const findings = validate({ mergedText: "save", ...ctx });
  assertEquals(findings.some((f) => f.category === "version-mismatch"), false);
});

Deno.test("validate - missing version on A disables key-drift check and warns", () => {
  const noHeader = DUMP_A.split("\n").slice(1).join("\n");
  const ctx = buildContext(noHeader, DUMP_B_NEWER);
  const merged = `# master\nset new_key_added_in_45 = 42\nsave`;
  const findings = validate({ mergedText: merged, ...ctx });
  assertEquals(findings.some((f) => f.category === "missing-version"), true);
  assertEquals(findings.some((f) => f.category === "unknown-key"), false);
});

Deno.test("validate - flags duplicate set keys in the merged output", () => {
  const ctx = buildContext(DUMP_A, DUMP_A);
  const merged = `# master\nset gyro_lpf1_static_hz = 0\nset gyro_lpf1_static_hz = 5\n\nsave`;
  const findings = validate({ mergedText: merged, ...ctx });
  const dup = findings.find((f) => f.category === "duplicate-key");
  assertEquals(dup !== undefined, true);
  assertEquals(dup.key, "gyro_lpf1_static_hz");
  assertEquals(dup.severity, "error");
});

Deno.test("validate - flags malformed set lines", () => {
  const ctx = buildContext(DUMP_A, DUMP_A);
  const merged = `# master\nset broken_no_equals\nset empty_value =\n\nsave`;
  const findings = validate({ mergedText: merged, ...ctx });
  const malformed = findings.filter((f) => f.category === "malformed-set");
  assertEquals(malformed.length, 2);
  assertEquals(malformed[0].severity, "error");
});

Deno.test("validate - warns when the merged output has no save terminator", () => {
  const ctx = buildContext(DUMP_A, DUMP_A);
  const merged = `# master\nset gyro_lpf1_static_hz = 0`;
  const findings = validate({ mergedText: merged, ...ctx });
  assertEquals(findings.some((f) => f.category === "missing-save"), true);
});

Deno.test("validate - accepts save on its own line as terminator", () => {
  const ctx = buildContext(DUMP_A, DUMP_A);
  const merged = `# master\nset gyro_lpf1_static_hz = 0\nsave`;
  const findings = validate({ mergedText: merged, ...ctx });
  assertEquals(findings.some((f) => f.category === "missing-save"), false);
});

Deno.test("validate - words starting with 'set' are not treated as set commands", () => {
  const ctx = buildContext(DUMP_A, DUMP_A);
  // settings, setpoint, setup are not the `set` command; they must not
  // produce malformed-set findings.
  const merged =
    `# master\nsettings blah\nsetpoint = 5\nsetup something\nset gyro_lpf1_static_hz = 0\nsave`;
  const findings = validate({ mergedText: merged, ...ctx });
  assertEquals(findings.some((f) => f.category === "malformed-set"), false);
});
