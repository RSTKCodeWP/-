/**
 * Contract tests for the cloud-relay plugin install job state machine.
 *
 * The job carries the install request through:
 *
 *   queued → commanded → downloading → verifying → installing → completed
 *
 * with `failed` and `cancelled` as terminal off-ramps from any stage.
 *
 * These tests pin:
 *   - the stage validator declares exactly the 8 stages above
 *   - the mutation argument shapes for createJob / advanceStage /
 *     cancelJob match the documented contract
 *   - cancelJob refuses to roll back a job already in `installing`
 *   - cancelJob is a no-op (not an error) on already-terminal jobs
 *   - the schema table shape mirrors the mutation surface
 *
 * Convex internal mutations cannot be executed directly without a
 * runtime; the contract is asserted against the source text. This
 * mirrors the cmdDroneStatus tests in this folder.
 */
import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";

const MUTATION_PATH = path.join(process.cwd(), "convex/cmdPluginInstallJobs.ts");
const SCHEMA_PATH = path.join(process.cwd(), "convex/schema.ts");

const EXPECTED_STAGES = [
  "queued",
  "commanded",
  "downloading",
  "verifying",
  "installing",
  "completed",
  "failed",
  "cancelled",
] as const;

describe("plugin install job stage validator", () => {
  it("declares exactly the eight documented stages", async () => {
    const text = await readFile(MUTATION_PATH, "utf8");
    for (const stage of EXPECTED_STAGES) {
      expect(text).toContain(`v.literal("${stage}")`);
    }
  });

  it("does not declare any stages outside the documented set", async () => {
    const text = await readFile(MUTATION_PATH, "utf8");
    // Pull every v.literal("...") string occurrence inside the stage
    // validator block; if a future change adds a new stage, the test
    // forces an explicit update here and in the doc comment.
    const stageBlockMatch = text.match(
      /const stageValidator = v\.union\(([\s\S]*?)\);/,
    );
    expect(stageBlockMatch).toBeTruthy();
    const block = stageBlockMatch ? stageBlockMatch[1] : "";
    const literals = Array.from(block.matchAll(/v\.literal\("([^"]+)"\)/g)).map(
      (m) => m[1],
    );
    expect(literals.sort()).toEqual([...EXPECTED_STAGES].sort());
  });
});

describe("createJob mutation contract", () => {
  it("requires deviceId, archiveId, and requestedPermissions", async () => {
    const text = await readFile(MUTATION_PATH, "utf8");
    // Find the createJob args block.
    const exportIdx = text.indexOf("export const createJob");
    expect(exportIdx).toBeGreaterThan(-1);
    const argsBlock = text.slice(exportIdx, exportIdx + 800);
    expect(argsBlock).toContain("deviceId: v.string()");
    expect(argsBlock).toContain('archiveId: v.id("plugin_archives")');
    expect(argsBlock).toContain("requestedPermissions: v.array(v.string())");
  });

  it("enforces ownership of both the drone and the archive", async () => {
    const text = await readFile(MUTATION_PATH, "utf8");
    expect(text).toContain("requireOwnedDroneByDeviceId(ctx, args.deviceId)");
    // The archive must belong to the same caller (userId === userId);
    // a missing archive throws "Archive not found".
    expect(text).toContain('throw new Error("Archive not found")');
  });

  it("auto-includes required permissions and refuses undeclared ones", async () => {
    const text = await readFile(MUTATION_PATH, "utf8");
    // Permission scope guard.
    expect(text).toContain(
      "was not declared in the manifest",
    );
    // Required permissions are folded into the effective set.
    expect(text).toContain(".filter((p) => p.required)");
  });

  it("transitions the job from queued to commanded after enqueue", async () => {
    const text = await readFile(MUTATION_PATH, "utf8");
    // Initial insert uses "queued"...
    expect(text).toContain('stage: "queued"');
    // ...and is patched to "commanded" once cmd_droneCommands row exists.
    expect(text).toContain('stage: "commanded"');
    expect(text).toContain('ctx.db.insert(\n      "plugin_install_jobs"');
    expect(text).toContain('ctx.db.insert(\n      "cmd_droneCommands"');
  });

  it("enforces a 5-minute hard ceiling on the signed download URL", async () => {
    const text = await readFile(MUTATION_PATH, "utf8");
    expect(text).toContain("SIGNED_URL_TTL_MS = 5 * 60 * 1000");
    expect(text).toContain("const signedUrlExpiresAt = now + SIGNED_URL_TTL_MS");
  });
});

describe("advanceStage mutation contract (agent-facing)", () => {
  it("is an internalMutation so only the HTTP layer can invoke it", async () => {
    const text = await readFile(MUTATION_PATH, "utf8");
    expect(text).toContain("export const advanceStage = internalMutation");
  });

  it("accepts a stage transition, an optional installId, and an optional error", async () => {
    const text = await readFile(MUTATION_PATH, "utf8");
    const exportIdx = text.indexOf("export const advanceStage");
    const argsBlock = text.slice(exportIdx, exportIdx + 500);
    expect(argsBlock).toContain('jobId: v.id("plugin_install_jobs")');
    expect(argsBlock).toContain("stage: stageValidator");
    expect(argsBlock).toContain('installId: v.optional(v.id("cmd_pluginInstalls"))');
    expect(argsBlock).toContain("error: v.optional(errorValidator)");
    expect(argsBlock).toContain("incrementAttempts: v.optional(v.boolean())");
  });
});

describe("cancelJob mutation contract", () => {
  it("is a no-op on already-terminal stages (completed, cancelled)", async () => {
    const text = await readFile(MUTATION_PATH, "utf8");
    expect(text).toContain(
      'if (job.stage === "completed" || job.stage === "cancelled") return',
    );
  });

  it("refuses to cancel a job already in the installing stage", async () => {
    const text = await readFile(MUTATION_PATH, "utf8");
    expect(text).toContain('if (job.stage === "installing")');
    expect(text).toContain("remove the plugin from the drone instead");
  });

  it("requires ownership on the job", async () => {
    const text = await readFile(MUTATION_PATH, "utf8");
    const cancelIdx = text.indexOf("export const cancelJob");
    const block = text.slice(cancelIdx, cancelIdx + 500);
    expect(block).toContain("getAuthUserId(ctx)");
    expect(block).toContain('throw new Error("Not authenticated")');
    expect(block).toContain('throw new Error("Job not found")');
  });
});

describe("plugin_install_jobs schema parity", () => {
  it("declares deviceId on the table so per-drone install lookup is possible", async () => {
    const text = await readFile(SCHEMA_PATH, "utf8");
    // Every plugin install job MUST carry the target drone's deviceId so
    // per-drone install lookups resolve to the right node. This test pins
    // the presence of that field on the table.
    const tableMatch = text.match(
      /plugin_install_jobs: defineTable\(\{([\s\S]*?)\}\)/,
    );
    expect(tableMatch).toBeTruthy();
    const tableBody = tableMatch ? tableMatch[1] : "";
    expect(tableBody).toContain("deviceId: v.string()");
  });

  it("indexes by deviceId+stage so the GCS can scan one drone's queue", async () => {
    const text = await readFile(SCHEMA_PATH, "utf8");
    expect(text).toContain(
      '.index("by_device_stage", ["deviceId", "stage"])',
    );
  });

  it("snapshots the full plugin_install_jobs field set", async () => {
    const text = await readFile(SCHEMA_PATH, "utf8");
    const tableStart = text.indexOf("plugin_install_jobs: defineTable({");
    expect(tableStart).toBeGreaterThan(-1);
    // Walk to the matching close brace at depth 0 starting from the
    // open paren of `defineTable(`.
    const openParen = text.indexOf("(", tableStart);
    let depth = 0;
    let close = -1;
    for (let i = openParen; i < text.length; i += 1) {
      const ch = text[i];
      if (ch === "(" || ch === "{") depth += 1;
      else if (ch === ")" || ch === "}") {
        depth -= 1;
        if (depth === 0) {
          close = i;
          break;
        }
      }
    }
    expect(close).toBeGreaterThan(-1);
    const tableBody = text.slice(openParen, close + 1);
    // Top-level fields are exactly the lines that, after comment strip
    // and whitespace trim, match `<name>: v.something`. Nested fields
    // inside v.object({...}) (`code`, `message`) are excluded because
    // they live one indent deeper than the top-level entries.
    const topLevelFields: string[] = [];
    for (const rawLine of tableBody.split("\n")) {
      const slash = rawLine.indexOf("//");
      const noComment = slash >= 0 ? rawLine.slice(0, slash) : rawLine;
      // Top-level fields are indented by 4 spaces inside defineTable({.
      const m = noComment.match(/^ {4}([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*v\./);
      if (m) topLevelFields.push(m[1]);
    }
    expect(Array.from(new Set(topLevelFields)).sort()).toMatchInlineSnapshot(`
      [
        "archiveId",
        "attempts",
        "cmdId",
        "createdAt",
        "deviceId",
        "error",
        "installId",
        "operatorId",
        "pluginId",
        "requestedPermissions",
        "stage",
        "updatedAt",
        "userId",
        "version",
      ]
    `);
  });
});
