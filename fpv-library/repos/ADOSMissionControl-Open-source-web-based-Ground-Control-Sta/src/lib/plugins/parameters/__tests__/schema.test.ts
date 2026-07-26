import { describe, it, expect, vi } from "vitest";

import {
  validateParameterSchema,
  validateValue,
  clampValue,
  inferWidget,
  resolveBinding,
  defaultFor,
  type ParameterSchema,
} from "../schema";
import { parseParameterContributions } from "../parse";

describe("validateParameterSchema", () => {
  it("accepts a well-formed numeric schema", () => {
    expect(
      validateParameterSchema({ type: "number", minimum: 2, maximum: 50, default: 8 }),
    ).toEqual({ ok: true });
  });

  it("rejects an unknown type", () => {
    const r = validateParameterSchema({ type: "object" });
    expect(r.ok).toBe(false);
  });

  it("rejects minimum > maximum", () => {
    const r = validateParameterSchema({ type: "number", minimum: 10, maximum: 1 });
    expect(r.ok).toBe(false);
  });

  it("rejects a non-positive step", () => {
    expect(validateParameterSchema({ type: "number", step: 0 }).ok).toBe(false);
  });

  it("rejects an empty enum and a bad regex", () => {
    expect(validateParameterSchema({ type: "string", enum: [] }).ok).toBe(false);
    expect(
      validateParameterSchema({ type: "string", pattern: "(" }).ok,
    ).toBe(false);
  });

  it("rejects a default that violates its own schema", () => {
    expect(
      validateParameterSchema({ type: "number", minimum: 0, maximum: 5, default: 9 })
        .ok,
    ).toBe(false);
  });
});

describe("validateValue", () => {
  const num: ParameterSchema = { type: "number", minimum: 0, maximum: 10 };
  it("enforces numeric bounds + integer-ness", () => {
    expect(validateValue(num, 5).ok).toBe(true);
    expect(validateValue(num, -1).ok).toBe(false);
    expect(validateValue(num, 11).ok).toBe(false);
    expect(validateValue({ type: "integer" }, 1.5).ok).toBe(false);
  });
  it("enforces enum membership over type", () => {
    const s: ParameterSchema = { type: "string", enum: ["a", "b"] };
    expect(validateValue(s, "a").ok).toBe(true);
    expect(validateValue(s, "z").ok).toBe(false);
  });
  it("enforces string pattern + boolean type", () => {
    expect(validateValue({ type: "string", pattern: "^x" }, "xy").ok).toBe(true);
    expect(validateValue({ type: "string", pattern: "^x" }, "zy").ok).toBe(false);
    expect(validateValue({ type: "boolean" }, true).ok).toBe(true);
    expect(validateValue({ type: "boolean" }, "true").ok).toBe(false);
  });
  it("tolerates an unknown schema keyword (forward-compatible)", () => {
    // A keyword the validator does not know is ignored, not rejected, so a
    // future manifest schema still validates against the known constraints.
    const s = {
      type: "number",
      minimum: 0,
      maximum: 10,
      futureKeyword: { nested: true },
    } as unknown as ParameterSchema;
    expect(validateValue(s, 5).ok).toBe(true);
    expect(validateValue(s, 11).ok).toBe(false);
  });
});

describe("clampValue", () => {
  it("clamps to bounds and quantizes to step", () => {
    const s: ParameterSchema = { type: "number", minimum: 0, maximum: 10, step: 2 };
    expect(clampValue(s, 11)).toBe(10);
    expect(clampValue(s, -3)).toBe(0);
    expect(clampValue(s, 3)).toBe(4); // 3 rounds to nearest step (4)
  });
  it("rounds integers and passes through strings/booleans", () => {
    expect(clampValue({ type: "integer" }, 2.6)).toBe(3);
    expect(clampValue({ type: "string" }, "hi")).toBe("hi");
    expect(clampValue({ type: "boolean" }, true)).toBe(true);
  });
});

describe("inferWidget / resolveBinding / defaultFor", () => {
  it("infers widgets and honors explicit ones", () => {
    expect(inferWidget({ type: "boolean" })).toBe("boolean");
    expect(inferWidget({ type: "number" })).toBe("number");
    expect(inferWidget({ type: "string", enum: ["a"] })).toBe("enum");
    expect(inferWidget({ type: "number" }, { widget: "range" })).toBe("range");
    expect(inferWidget({ type: "string" }, { widget: "model" })).toBe("model");
  });
  it("defaults the binding to plugin.config", () => {
    expect(resolveBinding({ key: "k", schema: { type: "number" } })).toBe(
      "plugin.config",
    );
    expect(
      resolveBinding({
        key: "k",
        schema: { type: "string" },
        binding: "engine.detector",
      }),
    ).toBe("engine.detector");
  });
  it("computes a type-appropriate default", () => {
    expect(defaultFor({ type: "number", minimum: 3 })).toBe(3);
    expect(defaultFor({ type: "boolean" })).toBe(false);
    expect(defaultFor({ type: "string", enum: ["a", "b"] })).toBe("a");
    expect(defaultFor({ type: "number", default: 7 })).toBe(7);
  });
});

describe("parseParameterContributions", () => {
  it("returns undefined for a non-array", () => {
    expect(parseParameterContributions(undefined)).toBeUndefined();
    expect(parseParameterContributions({})).toBeUndefined();
  });

  it("parses valid parameters with binding + ui", () => {
    const out = parseParameterContributions([
      {
        key: "follow_distance_m",
        schema: { type: "number", minimum: 2, maximum: 50, default: 8 },
        ui: { widget: "range", group: "Behavior", label: "Follow distance (m)" },
        binding: "plugin.config",
      },
      {
        key: "detector_model",
        schema: { type: "string" },
        ui: { widget: "model", task: "detection", group: "Perception" },
        binding: "engine.detector",
      },
    ]);
    expect(out).toHaveLength(2);
    expect(out![0].binding).toBe("plugin.config");
    expect(out![0].ui?.widget).toBe("range");
    expect(out![1].binding).toBe("engine.detector");
    expect(out![1].ui?.task).toBe("detection");
  });

  it("drops invalid entries and warns, never throws", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const out = parseParameterContributions([
      { schema: { type: "number" } }, // missing key
      { key: "bad", schema: { type: "object" } }, // bad schema type
      { key: "dup", schema: { type: "number" } },
      { key: "dup", schema: { type: "number" } }, // duplicate
      { key: "ok", schema: { type: "boolean" } },
    ]);
    expect(out).toHaveLength(2); // "dup" (first) + "ok"
    expect(out!.map((p) => p.key)).toEqual(["dup", "ok"]);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it("coerces an unknown binding to the default with a warning", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const out = parseParameterContributions([
      { key: "k", schema: { type: "number" }, binding: "nonsense" },
    ]);
    expect(out![0].binding).toBe("plugin.config");
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});
