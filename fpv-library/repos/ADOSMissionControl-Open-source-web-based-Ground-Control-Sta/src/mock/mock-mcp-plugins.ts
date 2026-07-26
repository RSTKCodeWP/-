/**
 * @module mock/mock-mcp-plugins
 * @description Demo-mode MCP plugin views for the console's Plugins segment, so
 * `npm run demo` renders the segment without a real agent or manifest fetch.
 * Generic synthetic plugins (a first-party follow behavior, an untrusted orbit
 * behavior, a first-party thermal camera). Never imported in a production path.
 * @license GPL-3.0-only
 */

import type { McpPluginView } from "@/lib/plugins/mcp-plugin-tools";

const DEMO_MCP_PLUGINS: McpPluginView[] = [
  {
    pluginId: "com.altnautica.follow-me",
    name: "Follow-Me",
    version: "0.2.1",
    firstParty: true,
    mcpExposed: true,
    grantedCaps: ["vision.detection.subscribe", "flight.guided_setpoint", "mcp.expose"],
    installedOn: ["demo-drone-01", "demo-drone-02"],
    tools: [
      {
        name: "start_follow",
        title: "Start follow",
        description: "Begin the follow behavior on the current locked track.",
        safetyClass: "flight_action",
        half: "agent",
        inputSchema: {
          type: "object",
          properties: { distance_m: { type: "number", description: "Follow distance in metres." } },
        },
      },
      {
        name: "stop_follow",
        title: "Stop follow",
        description: "Stop following and hold position.",
        safetyClass: "safe_write",
        half: "agent",
      },
      {
        name: "preview_follow_box",
        title: "Preview follow box",
        description: "Preview the follow box in the video overlay.",
        safetyClass: "read",
        half: "gcs",
      },
    ],
    resources: [{ uri: "follow/state", name: "Follow state", mimeType: "application/json" }],
    prompts: [{ name: "tune_follow", description: "Recommend a follow distance for this scene." }],
  },
  {
    pluginId: "com.example.orbit",
    name: "Orbit",
    version: "0.3.0",
    firstParty: false,
    mcpExposed: true,
    grantedCaps: ["flight.guided_setpoint", "mcp.expose"],
    installedOn: ["demo-drone-01"],
    tools: [
      {
        name: "start_orbit",
        title: "Start orbit",
        description: "Fly a circular orbit around the locked target.",
        safetyClass: "flight_action",
        half: "agent",
      },
      {
        name: "orbit_status",
        title: "Orbit status",
        description: "Report the current orbit radius and phase.",
        safetyClass: "read",
        half: "agent",
      },
    ],
    resources: [],
    prompts: [],
  },
  {
    pluginId: "com.altnautica.thermal-cam",
    name: "Thermal Camera",
    version: "1.1.0",
    firstParty: true,
    mcpExposed: false,
    grantedCaps: ["camera.read"],
    installedOn: ["demo-drone-02"],
    tools: [],
    resources: [],
    prompts: [],
  },
];

/** The demo MCP plugin views (a stable copy per call). */
export function getDemoMcpPlugins(): McpPluginView[] {
  return DEMO_MCP_PLUGINS.map((p) => ({ ...p }));
}
