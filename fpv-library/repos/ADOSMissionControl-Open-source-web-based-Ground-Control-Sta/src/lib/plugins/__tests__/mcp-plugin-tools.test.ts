import { describe, it, expect } from "vitest";
import {
  countExposedPlugins,
  filterPlugins,
  isFirstPartySigner,
  type McpPluginView,
} from "../mcp-plugin-tools";

const view = (over: Partial<McpPluginView> & { pluginId: string; name: string }): McpPluginView => ({
  version: "1.0.0",
  firstParty: false,
  mcpExposed: true,
  grantedCaps: [],
  installedOn: [],
  tools: [],
  resources: [],
  prompts: [],
  ...over,
});

describe("isFirstPartySigner", () => {
  it("matches the first-party allowlist form only", () => {
    expect(isFirstPartySigner("altnautica-2026-A")).toBe(true);
    expect(isFirstPartySigner("altnautica-2026-AB")).toBe(false);
    expect(isFirstPartySigner("example-2026-A")).toBe(false);
    expect(isFirstPartySigner(undefined)).toBe(false);
  });
});

describe("countExposedPlugins", () => {
  it("counts only plugins that expose MCP", () => {
    const plugins = [
      view({ pluginId: "a", name: "A", mcpExposed: true }),
      view({ pluginId: "b", name: "B", mcpExposed: false }),
      view({ pluginId: "c", name: "C", mcpExposed: true }),
    ];
    expect(countExposedPlugins(plugins)).toBe(2);
  });
});

describe("filterPlugins", () => {
  const plugins = [
    view({ pluginId: "com.x.follow", name: "Follow-Me" }),
    view({ pluginId: "com.x.orbit", name: "Orbit" }),
  ];
  it("matches by name or id, case-insensitive; empty query returns all", () => {
    expect(filterPlugins(plugins, "").map((p) => p.name)).toEqual(["Follow-Me", "Orbit"]);
    expect(filterPlugins(plugins, "orb").map((p) => p.name)).toEqual(["Orbit"]);
    expect(filterPlugins(plugins, "FOLLOW").map((p) => p.name)).toEqual(["Follow-Me"]);
    expect(filterPlugins(plugins, "com.x.orbit").map((p) => p.name)).toEqual(["Orbit"]);
    expect(filterPlugins(plugins, "zzz")).toEqual([]);
  });
});
