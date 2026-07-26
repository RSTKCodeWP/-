import { assertEquals, assertExists } from "https://deno.land/std@0.208.0/assert/mod.ts";
import { compareSections, parseCLI } from "../../cli-merge/src/parser.js";

const MINIMAL_CLI =
  `# Betaflight / STM32F745 (S745) 4.4.0 Nov  1 2022 / 01:00:00 (abc) MSP API: 1.45
# start the command batch
batch start

# feature
feature TELEMETRY

# serial
serial 0 64 115200 57600 0 115200

# master
set gyro_lpf1_static_hz = 0
set gyro_lpf2_static_hz = 500

profile 0

# profile
set dterm_lpf1_dyn_min_hz = 75

rateprofile 0

# rateprofile
set roll_rc_rate = 100

# restore original profile selection
profile 0

# restore original rateprofile selection
rateprofile 0

# save configuration
save`;

Deno.test("parseCLI - returns non-empty array", () => {
  const sections = parseCLI(MINIMAL_CLI);
  assertEquals(Array.isArray(sections), true);
  assertEquals(sections.length > 0, true);
});

Deno.test("parseCLI - extracts header with Betaflight line and batch start", () => {
  const sections = parseCLI(MINIMAL_CLI);
  const header = sections.find((s) => s.id === "header");
  assertExists(header);
  assertEquals(header.lines.some((l) => l.includes("Betaflight")), true);
  assertEquals(header.lines.some((l) => l.trim() === "batch start"), true);
});

Deno.test("parseCLI - extracts feature section", () => {
  const sections = parseCLI(MINIMAL_CLI);
  const feature = sections.find((s) => s.id === "feature");
  assertExists(feature);
  assertEquals(feature.lines.some((l) => l.includes("feature TELEMETRY")), true);
});

Deno.test("parseCLI - feature section does not contain the comment line", () => {
  const sections = parseCLI(MINIMAL_CLI);
  const feature = sections.find((s) => s.id === "feature");
  assertExists(feature);
  assertEquals(feature.lines.every((l) => l.trim() !== "# feature"), true);
});

Deno.test("parseCLI - extracts serial section", () => {
  const sections = parseCLI(MINIMAL_CLI);
  const serial = sections.find((s) => s.id === "serial");
  assertExists(serial);
  assertEquals(serial.lines.some((l) => l.startsWith("serial")), true);
});

Deno.test("parseCLI - extracts master section with set commands", () => {
  const sections = parseCLI(MINIMAL_CLI);
  const master = sections.find((s) => s.id === "master");
  assertExists(master);
  assertEquals(master.lines.some((l) => l.includes("set gyro_lpf1_static_hz")), true);
  assertEquals(master.lines.some((l) => l.includes("set gyro_lpf2_static_hz")), true);
});

Deno.test("parseCLI - extracts profile_0 section", () => {
  const sections = parseCLI(MINIMAL_CLI);
  const profile0 = sections.find((s) => s.id === "profile_0");
  assertExists(profile0);
  assertEquals(profile0.lines.some((l) => l.trim() === "profile 0"), true);
  assertEquals(profile0.lines.some((l) => l.includes("set dterm_lpf1_dyn_min_hz")), true);
});

Deno.test("parseCLI - profile_0 includes the sub-header comment", () => {
  const sections = parseCLI(MINIMAL_CLI);
  const profile0 = sections.find((s) => s.id === "profile_0");
  assertExists(profile0);
  assertEquals(profile0.lines.some((l) => l.trim() === "# profile"), true);
});

Deno.test("parseCLI - extracts rateprofile_0 section", () => {
  const sections = parseCLI(MINIMAL_CLI);
  const rp0 = sections.find((s) => s.id === "rateprofile_0");
  assertExists(rp0);
  assertEquals(rp0.lines.some((l) => l.trim() === "rateprofile 0"), true);
  assertEquals(rp0.lines.some((l) => l.includes("set roll_rc_rate")), true);
});

Deno.test("parseCLI - restore lines and save go to footer", () => {
  const sections = parseCLI(MINIMAL_CLI);
  const footer = sections.find((s) => s.id === "footer");
  assertExists(footer);
  assertEquals(footer.lines.some((l) => l.trim() === "save"), true);
  assertEquals(footer.lines.some((l) => l.includes("restore")), true);
});

Deno.test("parseCLI - no section has empty lines array", () => {
  const sections = parseCLI(MINIMAL_CLI);
  for (const sec of sections) {
    assertEquals(
      sec.lines.some((l) => l.trim()),
      true,
      `section ${sec.id} has no non-empty lines`,
    );
  }
});

// dump all format — top-level "# profile" / "# rateprofile" before the profile N command

const DUMP_ALL_CLI =
  `# Betaflight / STM32F745 (S745) 4.4.0 Nov  1 2022 / 01:00:00 (abc) MSP API: 1.45
# start the command batch
batch start

# feature
feature TELEMETRY

# master
set gyro_lpf1_static_hz = 0

# profile
profile 0

# profile
set dterm_lpf1_dyn_min_hz = 75

profile 1

# profile
set dterm_lpf1_dyn_min_hz = 80

# rateprofile
rateprofile 0

# rateprofile
set roll_rc_rate = 100

rateprofile 1

# rateprofile
set roll_rc_rate = 120

# save configuration
save`;

Deno.test("parseCLI dump-all - no spurious 'profile' section", () => {
  const sections = parseCLI(DUMP_ALL_CLI);
  assertEquals(sections.some((s) => s.id === "profile"), false);
});

Deno.test("parseCLI dump-all - no spurious 'rateprofile' section", () => {
  const sections = parseCLI(DUMP_ALL_CLI);
  assertEquals(sections.some((s) => s.id === "rateprofile"), false);
});

Deno.test("parseCLI dump-all - extracts profile_0 with settings", () => {
  const sections = parseCLI(DUMP_ALL_CLI);
  const p0 = sections.find((s) => s.id === "profile_0");
  assertExists(p0);
  assertEquals(p0.lines.some((l) => l.trim() === "profile 0"), true);
  assertEquals(p0.lines.some((l) => l.includes("set dterm_lpf1_dyn_min_hz = 75")), true);
});

Deno.test("parseCLI dump-all - extracts profile_1 with settings", () => {
  const sections = parseCLI(DUMP_ALL_CLI);
  const p1 = sections.find((s) => s.id === "profile_1");
  assertExists(p1);
  assertEquals(p1.lines.some((l) => l.trim() === "profile 1"), true);
  assertEquals(p1.lines.some((l) => l.includes("set dterm_lpf1_dyn_min_hz = 80")), true);
});

Deno.test("parseCLI dump-all - extracts rateprofile_0 with settings", () => {
  const sections = parseCLI(DUMP_ALL_CLI);
  const rp0 = sections.find((s) => s.id === "rateprofile_0");
  assertExists(rp0);
  assertEquals(rp0.lines.some((l) => l.trim() === "rateprofile 0"), true);
  assertEquals(rp0.lines.some((l) => l.includes("set roll_rc_rate = 100")), true);
});

Deno.test("parseCLI dump-all - extracts rateprofile_1 with settings", () => {
  const sections = parseCLI(DUMP_ALL_CLI);
  const rp1 = sections.find((s) => s.id === "rateprofile_1");
  assertExists(rp1);
  assertEquals(rp1.lines.some((l) => l.trim() === "rateprofile 1"), true);
  assertEquals(rp1.lines.some((l) => l.includes("set roll_rc_rate = 120")), true);
});

Deno.test("parseCLI dump-all vs diff-all - profile_0 sections are structurally equivalent", () => {
  const diffSections = parseCLI(MINIMAL_CLI);
  const dumpSections = parseCLI(DUMP_ALL_CLI);
  const diffP0 = diffSections.find((s) => s.id === "profile_0");
  const dumpP0 = dumpSections.find((s) => s.id === "profile_0");
  assertExists(diffP0);
  assertExists(dumpP0);
  // Both should have the profile switch command and the sub-header comment
  assertEquals(diffP0.lines.some((l) => l.trim() === "profile 0"), true);
  assertEquals(dumpP0.lines.some((l) => l.trim() === "profile 0"), true);
  assertEquals(diffP0.lines.some((l) => l.trim() === "# profile"), true);
  assertEquals(dumpP0.lines.some((l) => l.trim() === "# profile"), true);
});

// numbered sub-headers: "# profile N" / "# rateprofile N" (real-world format)

const NUMBERED_SUBHEADER_CLI = `# Betaflight / HUMMINGBIRD_F4_V4 4.5.1
# start the command batch
batch start

# master
set gyro_lpf2_static_hz = 1000

profile 0

# profile 0
set profile_name = AOS 65mm
set dterm_lpf1_dyn_min_hz = 75
set p_pitch = 95

profile 1

profile 2

# restore original profile selection
profile 0

rateprofile 0

# rateprofile 0
set rateprofile_name = DAILYRIP
set roll_rc_rate = 20
set roll_srate = 110

rateprofile 1

# rateprofile 1
set rateprofile_name = MID
set roll_rc_rate = 23

rateprofile 2

# restore original rate profile selection
rateprofile 0

# save configuration
save`;

Deno.test("parseCLI numbered subheader - no spurious 'profile 0' section", () => {
  const sections = parseCLI(NUMBERED_SUBHEADER_CLI);
  assertEquals(sections.some((s) => s.id === "profile 0"), false);
});

Deno.test("parseCLI numbered subheader - no spurious 'rateprofile 0' section", () => {
  const sections = parseCLI(NUMBERED_SUBHEADER_CLI);
  assertEquals(sections.some((s) => s.id === "rateprofile 0"), false);
});

Deno.test("parseCLI numbered subheader - no spurious 'rateprofile 1' section", () => {
  const sections = parseCLI(NUMBERED_SUBHEADER_CLI);
  assertEquals(sections.some((s) => s.id === "rateprofile 1"), false);
});

Deno.test("parseCLI numbered subheader - profile_0 contains switch command and settings", () => {
  const sections = parseCLI(NUMBERED_SUBHEADER_CLI);
  const p0 = sections.find((s) => s.id === "profile_0");
  assertExists(p0);
  assertEquals(p0.lines.some((l) => l.trim() === "profile 0"), true);
  assertEquals(p0.lines.some((l) => l.includes("set profile_name = AOS 65mm")), true);
  assertEquals(p0.lines.some((l) => l.includes("set dterm_lpf1_dyn_min_hz = 75")), true);
});

Deno.test("parseCLI numbered subheader - profile_0 sub-header kept inside section", () => {
  const sections = parseCLI(NUMBERED_SUBHEADER_CLI);
  const p0 = sections.find((s) => s.id === "profile_0");
  assertExists(p0);
  assertEquals(p0.lines.some((l) => l.trim() === "# profile 0"), true);
});

Deno.test("parseCLI numbered subheader - rateprofile_0 contains switch command and settings", () => {
  const sections = parseCLI(NUMBERED_SUBHEADER_CLI);
  const rp0 = sections.find((s) => s.id === "rateprofile_0");
  assertExists(rp0);
  assertEquals(rp0.lines.some((l) => l.trim() === "rateprofile 0"), true);
  assertEquals(rp0.lines.some((l) => l.includes("set rateprofile_name = DAILYRIP")), true);
});

Deno.test("parseCLI numbered subheader - rateprofile_1 contains its own settings", () => {
  const sections = parseCLI(NUMBERED_SUBHEADER_CLI);
  const rp1 = sections.find((s) => s.id === "rateprofile_1");
  assertExists(rp1);
  assertEquals(rp1.lines.some((l) => l.trim() === "rateprofile 1"), true);
  assertEquals(rp1.lines.some((l) => l.includes("set rateprofile_name = MID")), true);
});

Deno.test("parseCLI numbered subheader - profile_0 settings not in master", () => {
  const sections = parseCLI(NUMBERED_SUBHEADER_CLI);
  const master = sections.find((s) => s.id === "master");
  assertExists(master);
  assertEquals(master.lines.some((l) => l.includes("set profile_name")), false);
  assertEquals(master.lines.some((l) => l.includes("set dterm_lpf1_dyn_min_hz")), false);
});

Deno.test("parseCLI numbered subheader - restore-before-rateprofiles: rateprofiles are sections not footer", () => {
  // Betaflight 4.5+ places '# restore original profile selection' + 'profile 0'
  // BEFORE the rateprofile sections. The parser must not open footer early.
  const sections = parseCLI(NUMBERED_SUBHEADER_CLI);
  assertEquals(sections.some((s) => s.id === "rateprofile_0"), true);
  assertEquals(sections.some((s) => s.id === "rateprofile_1"), true);
  const footer = sections.find((s) => s.id === "footer");
  assertExists(footer);
  // Footer should have the restore lines but not the rate settings
  assertEquals(footer.lines.some((l) => l.includes("restore")), true);
  assertEquals(footer.lines.some((l) => l.includes("set rateprofile_name")), false);
});

// compareSections

Deno.test("compareSections - identical input yields all 'same'", () => {
  const sections = parseCLI(MINIMAL_CLI);
  const compared = compareSections(sections, sections);
  for (const sec of compared) {
    assertEquals(sec.status, "same", `expected same for ${sec.id}`);
  }
});

Deno.test("compareSections - section only in A is 'only-a'", () => {
  const a = [{ id: "feature", title: "feature", lines: ["feature TELEMETRY"] }];
  const b: never[] = [];
  const compared = compareSections(a, b);
  assertEquals(compared[0].status, "only-a");
  assertEquals(compared[0].linesA, ["feature TELEMETRY"]);
  assertEquals(compared[0].linesB, []);
});

Deno.test("compareSections - section only in B is 'only-b'", () => {
  const a: never[] = [];
  const b = [{ id: "beacon", title: "beacon", lines: ["beacon RX_LOST"] }];
  const compared = compareSections(a, b);
  assertEquals(compared[0].status, "only-b");
  assertEquals(compared[0].linesA, []);
  assertEquals(compared[0].linesB, ["beacon RX_LOST"]);
});

Deno.test("compareSections - different content is 'diff'", () => {
  const a = [{ id: "master", title: "master", lines: ["set gyro_lpf1_static_hz = 0"] }];
  const b = [{ id: "master", title: "master", lines: ["set gyro_lpf1_static_hz = 100"] }];
  const compared = compareSections(a, b);
  assertEquals(compared[0].status, "diff");
  assertEquals(compared[0].linesA, ["set gyro_lpf1_static_hz = 0"]);
  assertEquals(compared[0].linesB, ["set gyro_lpf1_static_hz = 100"]);
});

Deno.test("compareSections - order: A sections first, then B-only sections", () => {
  const a = [
    { id: "feature", title: "feature", lines: ["feature A"] },
    { id: "serial", title: "serial", lines: ["serial 0"] },
  ];
  const b = [
    { id: "feature", title: "feature", lines: ["feature A"] },
    { id: "beacon", title: "beacon", lines: ["beacon RX_LOST"] },
  ];
  const compared = compareSections(a, b);
  assertEquals(compared[0].id, "feature");
  assertEquals(compared[1].id, "serial");
  assertEquals(compared[2].id, "beacon");
});

Deno.test("compareSections - exposes both linesA and linesB for diff sections", () => {
  const a = [{ id: "feature", title: "feature", lines: ["feature TELEMETRY"] }];
  const b = [{ id: "feature", title: "feature", lines: ["feature RX_PPM"] }];
  const compared = compareSections(a, b);
  assertEquals(compared[0].linesA, ["feature TELEMETRY"]);
  assertEquals(compared[0].linesB, ["feature RX_PPM"]);
});

Deno.test("compareSections - footer is always last even when B has extra sections", () => {
  const a = [
    { id: "master", title: "master", lines: ["set x = 1"] },
    { id: "footer", title: "Footer", lines: ["save"] },
  ];
  const b = [
    { id: "master", title: "master", lines: ["set x = 1"] },
    { id: "feature", title: "feature", lines: ["feature OSD"] },
    { id: "footer", title: "Footer", lines: ["save"] },
  ];
  const compared = compareSections(a, b);
  assertEquals(compared[compared.length - 1].id, "footer");
});

// OSD extraction

const CLI_WITH_OSD_IN_MASTER = `# Betaflight / STM32F745 4.4.0
# start the command batch
batch start

# master
set gyro_lpf1_static_hz = 0
set osd_vbat_pos = 6177
set osd_rssi_pos = 353
set gyro_lpf2_static_hz = 500
set osd_craft_name_pos = 6151

# save configuration
save`;

Deno.test("parseCLI - osd_* lines extracted from master into osd section", () => {
  const sections = parseCLI(CLI_WITH_OSD_IN_MASTER);
  const osd = sections.find((s) => s.id === "osd");
  assertExists(osd);
  assertEquals(osd.lines.some((l) => l.includes("set osd_vbat_pos = 6177")), true);
  assertEquals(osd.lines.some((l) => l.includes("set osd_rssi_pos = 353")), true);
  assertEquals(osd.lines.some((l) => l.includes("set osd_craft_name_pos = 6151")), true);
});

Deno.test("parseCLI - master section does not contain osd_* lines after extraction", () => {
  const sections = parseCLI(CLI_WITH_OSD_IN_MASTER);
  const master = sections.find((s) => s.id === "master");
  assertExists(master);
  assertEquals(master.lines.every((l) => !/^set\s+osd_/.test(l.trim())), true);
  assertEquals(master.lines.some((l) => l.includes("set gyro_lpf1_static_hz")), true);
});

Deno.test("parseCLI - osd section appears immediately after master", () => {
  const sections = parseCLI(CLI_WITH_OSD_IN_MASTER);
  const masterIdx = sections.findIndex((s) => s.id === "master");
  const osdIdx = sections.findIndex((s) => s.id === "osd");
  assertExists(sections[masterIdx]);
  assertExists(sections[osdIdx]);
  assertEquals(osdIdx, masterIdx + 1);
});

Deno.test("parseCLI - no osd section created when no osd_* settings present", () => {
  const sections = parseCLI(MINIMAL_CLI);
  assertEquals(sections.some((s) => s.id === "osd"), false);
});

// Native # osd section (newer Betaflight dumps already have a dedicated section)

const CLI_WITH_NATIVE_OSD = `# Betaflight / STM32F745 4.5.0
# start the command batch
batch start

# master
set gyro_lpf1_static_hz = 0

# osd
set osd_vbat_pos = 6177
set osd_rssi_pos = 353

# save configuration
save`;

const CLI_WITH_NATIVE_OSD_AND_MASTER_OSD = `# Betaflight / STM32F745 4.5.0
# start the command batch
batch start

# master
set gyro_lpf1_static_hz = 0
set osd_craft_name_pos = 6151

# osd
set osd_vbat_pos = 6177

# save configuration
save`;

Deno.test("parseCLI - native osd section is preserved as-is", () => {
  const sections = parseCLI(CLI_WITH_NATIVE_OSD);
  const osd = sections.find((s) => s.id === "osd");
  assertExists(osd);
  assertEquals(osd.lines.some((l) => l.includes("set osd_vbat_pos = 6177")), true);
  assertEquals(osd.lines.some((l) => l.includes("set osd_rssi_pos = 353")), true);
});

Deno.test("parseCLI - native osd section: master stays clean", () => {
  const sections = parseCLI(CLI_WITH_NATIVE_OSD);
  const master = sections.find((s) => s.id === "master");
  assertExists(master);
  assertEquals(master.lines.every((l) => !/^set\s+osd_/.test(l.trim())), true);
});

Deno.test("parseCLI - osd_* lines from master are merged into native osd section", () => {
  const sections = parseCLI(CLI_WITH_NATIVE_OSD_AND_MASTER_OSD);
  const osd = sections.find((s) => s.id === "osd");
  assertExists(osd);
  assertEquals(osd.lines.some((l) => l.includes("set osd_vbat_pos = 6177")), true);
  assertEquals(osd.lines.some((l) => l.includes("set osd_craft_name_pos = 6151")), true);
  assertEquals(sections.filter((s) => s.id === "osd").length, 1);
});

Deno.test("parseCLI - master has no osd_* after merge into native osd section", () => {
  const sections = parseCLI(CLI_WITH_NATIVE_OSD_AND_MASTER_OSD);
  const master = sections.find((s) => s.id === "master");
  assertExists(master);
  assertEquals(master.lines.every((l) => !/^set\s+osd_/.test(l.trim())), true);
});
