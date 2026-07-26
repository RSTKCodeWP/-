/**
 * Smoke tests for the cmd_droneStatus table shape and the pushStatus
 * mutation surface. The Convex schema is statically-typed but Convex's
 * runtime validators are only exercised at deploy time — these tests
 * pin the surface so a missing field on either side (table definition
 * or mutation args) gets caught locally.
 *
 * The test reads the source text of convex/schema.ts and
 * convex/cmdDroneStatus.ts and asserts that every field name we expect
 * to flow from agent heartbeat -> mutation args -> table row is present.
 */
import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SCHEMA_PATH = path.join(process.cwd(), "convex/schema.ts");
const MUTATION_PATH = path.join(process.cwd(), "convex/cmdDroneStatus.ts");

const NEW_OPTIONAL_FIELDS = [
  "lcdActivePage",
  "lcdTouchCalibrated",
  "lcdRotation",
  "lcdSnapshotUrl",
  "lcdLastTouchAt",
  "lcdLastGesture",
  "videoLocalDecoderActive",
  "videoLocalDecoderType",
  "videoLocalDecoderFps",
  "videoRecording",
  "uiTheme",
] as const;

const FIELD_VALIDATOR: Record<(typeof NEW_OPTIONAL_FIELDS)[number], string> = {
  lcdActivePage: "v.optional(v.string())",
  lcdTouchCalibrated: "v.optional(v.boolean())",
  lcdRotation: "v.optional(v.number())",
  lcdSnapshotUrl: "v.optional(v.string())",
  lcdLastTouchAt: "v.optional(v.number())",
  lcdLastGesture: "v.optional(v.string())",
  videoLocalDecoderActive: "v.optional(v.boolean())",
  videoLocalDecoderType: "v.optional(v.string())",
  videoLocalDecoderFps: "v.optional(v.number())",
  videoRecording: "v.optional(v.boolean())",
  uiTheme: "v.optional(v.string())",
};

describe("cmd_droneStatus schema", () => {
  it("declares the cmd_droneStatus table", async () => {
    const text = await readFile(SCHEMA_PATH, "utf8");
    expect(text).toContain("cmd_droneStatus: defineTable");
    expect(text).toContain('.index("by_deviceId", ["deviceId"])');
  });

  it.each(NEW_OPTIONAL_FIELDS)(
    "schema declares %s as an optional field with the expected validator",
    async (field) => {
      const text = await readFile(SCHEMA_PATH, "utf8");
      const expected = `${field}: ${FIELD_VALIDATOR[field]}`;
      expect(text).toContain(expected);
    },
  );

  it("preserves the radio block and existing identifier fields", async () => {
    const text = await readFile(SCHEMA_PATH, "utf8");
    expect(text).toContain("deviceId: v.string(),");
    expect(text).toContain("version: v.string(),");
    expect(text).toContain("uptimeSeconds: v.number(),");
    expect(text).toContain("radio: v.optional(v.object({");
    expect(text).toContain("updatedAt: v.number(),");
  });
});

describe("cmd_droneStatus mutation surface", () => {
  it("exports pushStatus as an internalMutation", async () => {
    const text = await readFile(MUTATION_PATH, "utf8");
    expect(text).toContain("export const pushStatus = internalMutation");
  });
});
