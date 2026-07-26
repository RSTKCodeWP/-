import { assertEquals } from "https://deno.land/std@0.208.0/assert/mod.ts";
import { buildOutput, parseSetCommands } from "../../cli-merge/src/output.js";

// parseSetCommands

Deno.test("parseSetCommands - extracts set key/value pairs", () => {
  const { sets, other } = parseSetCommands([
    "set gyro_lpf1_static_hz = 0",
    "set gyro_lpf2_static_hz = 500",
  ]);
  assertEquals(sets.get("gyro_lpf1_static_hz"), "0");
  assertEquals(sets.get("gyro_lpf2_static_hz"), "500");
  assertEquals(other.length, 0);
});

Deno.test("parseSetCommands - separates non-set lines into other", () => {
  const { sets, other } = parseSetCommands([
    "profile 0",
    "# profile",
    "set roll_rc_rate = 100",
  ]);
  assertEquals(sets.get("roll_rc_rate"), "100");
  assertEquals(other.includes("profile 0"), true);
  assertEquals(other.includes("# profile"), true);
});

Deno.test("parseSetCommands - handles values with spaces", () => {
  const { sets } = parseSetCommands(["set name = some value with spaces"]);
  assertEquals(sets.get("name"), "some value with spaces");
});

// buildOutput

Deno.test("buildOutput - sel 'a' uses A lines", () => {
  const sections = [
    {
      id: "feature",
      title: "feature",
      linesA: ["feature TELEMETRY"],
      linesB: ["feature RX_PPM"],
      status: "diff",
    },
  ];
  const out = buildOutput(sections, { feature: "a" }, {});
  assertEquals(out.includes("feature TELEMETRY"), true);
  assertEquals(out.includes("feature RX_PPM"), false);
});

Deno.test("buildOutput - sel 'b' uses B lines", () => {
  const sections = [
    {
      id: "feature",
      title: "feature",
      linesA: ["feature TELEMETRY"],
      linesB: ["feature RX_PPM"],
      status: "diff",
    },
  ];
  const out = buildOutput(sections, { feature: "b" }, {});
  assertEquals(out.includes("feature TELEMETRY"), false);
  assertEquals(out.includes("feature RX_PPM"), true);
});

Deno.test("buildOutput - sel 'skip' omits section entirely", () => {
  const sections = [
    {
      id: "feature",
      title: "feature",
      linesA: ["feature TELEMETRY"],
      linesB: [],
      status: "only-a",
    },
  ];
  const out = buildOutput(sections, { feature: "skip" }, {});
  assertEquals(out.includes("feature"), false);
});

Deno.test("buildOutput - adds # section comment header for regular sections", () => {
  const sections = [
    {
      id: "feature",
      title: "feature",
      linesA: ["feature TELEMETRY"],
      linesB: [],
      status: "only-a",
    },
  ];
  const out = buildOutput(sections, { feature: "a" }, {});
  assertEquals(out.includes("# feature"), true);
});

Deno.test("buildOutput - no comment header for header section", () => {
  const sections = [
    {
      id: "header",
      title: "Header",
      linesA: ["# Betaflight", "batch start"],
      linesB: [],
      status: "only-a",
    },
  ];
  const out = buildOutput(sections, { header: "a" }, {});
  assertEquals(out.includes("# Header"), false);
});

Deno.test("buildOutput - no comment header for footer section", () => {
  const sections = [
    { id: "footer", title: "Footer", linesA: ["save"], linesB: [], status: "only-a" },
  ];
  const out = buildOutput(sections, { footer: "a" }, {});
  assertEquals(out.includes("# Footer"), false);
});

Deno.test("buildOutput - no comment header for profile sections", () => {
  const sections = [
    {
      id: "profile_0",
      title: "Profile 0",
      linesA: ["profile 0", "# profile", "set x = 1"],
      linesB: [],
      status: "only-a",
    },
  ];
  const out = buildOutput(sections, { profile_0: "a" }, {});
  assertEquals(out.includes("# Profile 0"), false);
});

Deno.test("buildOutput - 'both' unions non-set lines", () => {
  const sections = [
    {
      id: "feature",
      title: "feature",
      linesA: ["feature TELEMETRY"],
      linesB: ["feature RX_PPM"],
      status: "diff",
    },
  ];
  const out = buildOutput(sections, { feature: "both" }, {});
  assertEquals(out.includes("feature TELEMETRY"), true);
  assertEquals(out.includes("feature RX_PPM"), true);
});

Deno.test("buildOutput - 'both' deduplicates lines present in both", () => {
  const sections = [
    {
      id: "feature",
      title: "feature",
      linesA: ["feature TELEMETRY", "feature RX_PPM"],
      linesB: ["feature TELEMETRY", "feature GPS"],
      status: "diff",
    },
  ];
  const out = buildOutput(sections, { feature: "both" }, {});
  const matches = out.match(/feature TELEMETRY/g);
  assertEquals(matches?.length, 1);
});

Deno.test("buildOutput - 'both' uses per-key setSelections for set sections", () => {
  const sections = [
    {
      id: "master",
      title: "master",
      linesA: ["set gyro_lpf1_static_hz = 0", "set gyro_lpf2_static_hz = 500"],
      linesB: ["set gyro_lpf1_static_hz = 100", "set gyro_lpf2_static_hz = 500"],
      status: "diff",
    },
  ];
  const out = buildOutput(
    sections,
    { master: "both" },
    { "master:gyro_lpf1_static_hz": "b", "master:gyro_lpf2_static_hz": "a" },
  );
  assertEquals(out.includes("set gyro_lpf1_static_hz = 100"), true);
  assertEquals(out.includes("set gyro_lpf2_static_hz = 500"), true);
});

Deno.test("buildOutput - 'both' set merge defaults missing key to A value", () => {
  const sections = [
    {
      id: "master",
      title: "master",
      linesA: ["set gyro_lpf1_static_hz = 0"],
      linesB: ["set gyro_lpf1_static_hz = 100"],
      status: "diff",
    },
  ];
  const out = buildOutput(sections, { master: "both" }, {}); // no explicit setSelection
  assertEquals(out.includes("set gyro_lpf1_static_hz = 0"), true);
});

Deno.test("buildOutput - 'both' includes set keys only in B", () => {
  const sections = [
    {
      id: "master",
      title: "master",
      linesA: ["set gyro_lpf1_static_hz = 0"],
      linesB: ["set gyro_lpf1_static_hz = 0", "set gyro_lpf2_static_hz = 500"],
      status: "diff",
    },
  ];
  const out = buildOutput(sections, { master: "both" }, {});
  assertEquals(out.includes("set gyro_lpf2_static_hz = 500"), true);
});

Deno.test("buildOutput - defaults only-a section to A without explicit selection", () => {
  const sections = [
    { id: "beacon", title: "beacon", linesA: ["beacon RX_LOST"], linesB: [], status: "only-a" },
  ];
  const out = buildOutput(sections, {}, {});
  assertEquals(out.includes("beacon RX_LOST"), true);
});

Deno.test("buildOutput - defaults only-b section to B without explicit selection", () => {
  const sections = [
    { id: "beacon", title: "beacon", linesA: [], linesB: ["beacon RX_LOST"], status: "only-b" },
  ];
  const out = buildOutput(sections, {}, {});
  assertEquals(out.includes("beacon RX_LOST"), true);
});

Deno.test("buildOutput - rateprofile section includes rateprofile switch command", () => {
  const sections = [
    {
      id: "rateprofile_1",
      title: "Rate Profile 1",
      linesA: [],
      linesB: ["rateprofile 1", "# rateprofile", "set roll_rc_rate = 120"],
      status: "only-b",
    },
  ];
  const out = buildOutput(sections, { rateprofile_1: "b" }, {});
  assertEquals(out.includes("rateprofile 1"), true);
  assertEquals(out.includes("set roll_rc_rate = 120"), true);
  assertEquals(out.indexOf("rateprofile 1") < out.indexOf("set roll_rc_rate = 120"), true);
});

Deno.test("buildOutput - profile section includes profile switch command", () => {
  const sections = [
    {
      id: "profile_1",
      title: "Profile 1",
      linesA: [],
      linesB: ["profile 1", "# profile", "set dterm_lpf1_dyn_min_hz = 80"],
      status: "only-b",
    },
  ];
  const out = buildOutput(sections, { profile_1: "b" }, {});
  assertEquals(out.includes("profile 1"), true);
  assertEquals(out.includes("set dterm_lpf1_dyn_min_hz = 80"), true);
  assertEquals(out.indexOf("profile 1") < out.indexOf("set dterm_lpf1_dyn_min_hz = 80"), true);
});
