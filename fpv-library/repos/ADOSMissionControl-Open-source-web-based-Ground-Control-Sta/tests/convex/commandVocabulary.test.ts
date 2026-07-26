/**
 * Contract tests for the cloud-relay command vocabulary.
 *
 * enqueueCommand validates the command name against this union at the queue
 * boundary so a typo or a forged name cannot land a dead row. These tests pin
 * (a) that the union validator accepts every permitted name and rejects an
 * unknown one at runtime, and (b) that enqueueCommand wires the validator
 * instead of a free-form v.string().
 */
import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";

import {
  RELAY_COMMAND_NAMES,
  RELAY_COMMAND_SCOPE,
  relayCommandValidator,
  requiredScopeForCommand,
} from "../../convex/commandVocabulary";

describe("relay command vocabulary", () => {
  it("includes the plugin lifecycle, WFB pairing, and status-pull commands", () => {
    // The set the agent dispatcher acts on + the GCS call sites queue.
    for (const name of [
      "plugin.install",
      "plugin.enable",
      "plugin.disable",
      "plugin.uninstall",
      "wfb_pair_init_remote",
      "wfb_pair_apply_remote",
      "wfb_pair_unpair",
      "get_peripherals",
      "scan_peripherals",
      "get_enrollment",
      "get_peers",
      "get_services",
      "get_logs",
      "restart_service",
      "send_command",
    ]) {
      expect(RELAY_COMMAND_NAMES).toContain(name);
    }
  });

  it("exposes a union validator over exactly the permitted names", () => {
    // The validator's member literals must match the name list one-for-one so
    // adding a name in the array keeps the validator in sync.
    expect(relayCommandValidator.kind).toBe("union");
    const literals = relayCommandValidator.members.map(
      (m: { value: unknown }) => m.value,
    );
    expect([...literals].sort()).toEqual([...RELAY_COMMAND_NAMES].sort());
  });

  it("has no duplicate names", () => {
    const unique = new Set(RELAY_COMMAND_NAMES);
    expect(unique.size).toBe(RELAY_COMMAND_NAMES.length);
  });
});

describe("relay command scope classes", () => {
  it("assigns every relay command a scope class (exhaustive map)", () => {
    for (const name of RELAY_COMMAND_NAMES) {
      expect(RELAY_COMMAND_SCOPE[name]).toBeDefined();
    }
  });

  it("classifies read pulls as read and admin ops as admin", () => {
    expect(requiredScopeForCommand("get_logs", {})).toBe("read");
    expect(requiredScopeForCommand("get_peers", {})).toBe("read");
    expect(requiredScopeForCommand("restart_service", {})).toBe("admin");
    expect(requiredScopeForCommand("plugin.install", {})).toBe("admin");
    expect(requiredScopeForCommand("scan_peripherals", {})).toBe("safe_write");
  });

  it("escalates a flight-shaped send_command to the flight scope", () => {
    for (const cmd of ["arm", "takeoff", "set_mode", "flight.land", "goto", "nav_takeoff"]) {
      expect(requiredScopeForCommand("send_command", { cmd })).toBe("flight");
    }
  });

  it("keeps a non-flight send_command at admin, and fails safe on a bad payload", () => {
    expect(requiredScopeForCommand("send_command", { cmd: "get_battery" })).toBe("admin");
    expect(requiredScopeForCommand("send_command", {})).toBe("admin");
    expect(requiredScopeForCommand("send_command", { cmd: 123 })).toBe("admin");
    expect(requiredScopeForCommand("send_command", null)).toBe("admin");
  });
});

describe("enqueueCommand command-name gate", () => {
  it("validates command against the vocabulary instead of a free-form string", async () => {
    const text = await readFile(
      path.join(process.cwd(), "convex/cmdDroneCommands.ts"),
      "utf8",
    );
    expect(text).toContain('import { relayCommandValidator } from "./commandVocabulary"');
    expect(text).toContain("command: relayCommandValidator,");
    // The free-form validator must be gone from the public enqueue boundary.
    expect(text).not.toContain("command: v.string(),");
  });
});
