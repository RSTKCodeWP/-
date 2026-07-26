/**
 * @module mock/demo-plugin-registry
 * @description A small, self-contained plugin-registry fixture for demo mode.
 * The live registry grid is Convex-backed and unreachable under `npm run demo`,
 * so this fixture lets the operator open the install / detail pop-up against
 * representative manifests and see the full revamped surface — badges, skills,
 * MCP tools, contributed panels, capability chips, permissions, and
 * screenshots — with no backend.
 *
 * The manifests mirror the shipped first-party extensions (their contributions
 * are public in the extensions repo); the optical-pod entry is lightly enriched
 * with a top-level icon, screenshots, and MCP tools so the demo exercises every
 * pop-up section. Nothing here reaches an agent — it is display data only.
 *
 * @license GPL-3.0-only
 */

import type { RegistryPluginRow } from "@/components/dashboard/drone-plugins/RegistryPluginCard";

/** A demo registry entry: the catalog row plus the manifest text and the
 * signing/download fields the install pop-up reads. */
export interface DemoRegistryEntry {
  row: RegistryPluginRow;
  manifestYaml: string;
  downloadUrl: string;
  archiveSha256: string;
  signerKeyId: string;
}

/** A labeled placeholder screenshot as an inline SVG data URI (renders offline). */
function shot(label: string): string {
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='320' height='180'><rect width='100%' height='100%' fill='%23151a22'/><rect x='8' y='8' width='304' height='164' rx='8' fill='none' stroke='%232b3646'/><text x='20' y='100' fill='%237c8aa0' font-family='sans-serif' font-size='15'>${label}</text></svg>`;
  return `data:image/svg+xml;utf8,${svg}`;
}

const SIYI_MANIFEST = `schema_version: 3
id: com.altnautica.siyi-pod
name: "ADOS SIYI Optical Pod"
version: "0.3.1"
icon: "camera"
description: "Native driver for the SIYI optical-pod line with per-model capability negotiation: gimbal, zoom, focus, photo/record, thermal palette and spot temperature, laser rangefinder with subject geolocation, and on-pod AI tracking."
description_long: |
  Speaks the SIYI Gimbal Camera External SDK over UDP, TCP, or a TTL serial
  port directly, so the agent drives the features a stock autopilot mount
  cannot: thermal palettes and temperature, the laser rangefinder, subject
  geolocation, and AI tracking. On start the plugin queries the hardware id,
  resolves the exact model's capability profile, and exposes only the controls
  that model supports.
features:
  - "Auto-detects the pod model and negotiates capabilities"
  - "Gimbal aim, rate, recenter, and lock/follow/FPV modes"
  - "Optical and absolute zoom, autofocus (zoom models)"
  - "Thermal palette, gain, and spot temperature (thermal models)"
  - "Laser rangefinder with subject geolocation on the map (laser models)"
  - "On-pod AI tracking republished to the cockpit (no accelerator required)"
hardware_requirements:
  cameras: "A SIYI optical pod on the pod network (192.168.144.x) or a TTL serial port"
  boards: ["cm4", "cm5", "rk3588s2", "rk3576", "rpi5", "x86"]
resource_impact:
  cpu_percent_peak: 12
  ram_mb: 96
  pids: 4
  output_rate_hz: 5
  startup_time_seconds: 3
telemetry_fields:
  - "siyi"
documentation_url: "https://docs.altnautica.com/drone-agent/siyi-pod-overview"
homepage: "https://github.com/altnautica/ADOSExtensions/tree/main/extensions/siyi-pod"
author: "Altnautica"
license: "GPL-3.0-or-later"
risk: high
screenshots:
  - url: "${shot("Pod control console")}"
    caption: "Pod control console"
  - url: "${shot("Laser target on the map")}"
    caption: "Laser target on the map"
agent:
  runtime: python
  permissions:
    - id: network.outbound
    - id: hardware.uart
    - id: mavlink.read
    - id: mavlink.write
    - id: mavlink.component.gimbal
    - id: mavlink.component.camera
    - id: sensor.camera.register
    - id: vision.detection.publish
    - id: vision.track.designate
    - id: video.source.set
    - id: event.publish
    - id: mcp.expose
  contributes:
    tools:
      - name: status
        description: "Read the pod's live state (mode, zoom, palette, tracking)."
        safety_class: read
      - name: set_zoom
        description: "Set the optical zoom level."
        safety_class: safe_write
        inputSchema:
          type: object
          properties:
            level:
              type: number
              minimum: 1
              maximum: 30
      - name: set_palette
        description: "Select the thermal colour palette."
        safety_class: safe_write
      - name: capture_photo
        description: "Capture a still to the pod's storage."
        safety_class: safe_write
      - name: geolocate_target
        description: "Fire the rangefinder and resolve the subject latitude and longitude."
        safety_class: safe_write
gcs:
  permissions:
    - id: ui.slot.node-detail-tab
    - id: ui.slot.cockpit-panel
    - id: ui.slot.video-overlay
    - id: ui.slot.flight-skill
    - id: ui.slot.map-overlay
    - id: ui.slot.notification-channel
    - id: telemetry.subscribe.siyi
    - id: command.send
  contributes:
    tabs:
      - id: siyi-console
        slot: node.detail.tab
        profile: ["drone"]
        title: "SIYI Pod"
        icon: "camera"
        order: 55
    panels:
      - id: siyi-cockpit
        slot: cockpit.panel
        title: "Pod"
        icon: "camera"
        order: 40
      - id: siyi-overlay
        slot: video.overlay
        title: "SIYI pod HUD"
        icon: "crosshair"
      - id: siyi-map
        slot: map.overlay
        title: "Laser target"
        icon: "target"
    notifications:
      - id: siyi-health
        title: "SIYI pod health"
        severity: warning
    skills:
      - id: siyi-track
        label: "skill.track"
        icon: "crosshair"
        category: camera
        toggle: true
        arm_requirement: any
        default_binding: { key: "t" }
        activation: { via: config, config_key: track_active }
        state: { via: event, topic: "siyi.pod.state" }
      - id: siyi-record
        label: "skill.record"
        icon: "video"
        category: camera
        toggle: true
        arm_requirement: any
        default_binding: { key: "r" }
        activation: { via: config, config_key: recording }
        state: { via: event, topic: "siyi.pod.state" }
    target_actions:
      - id: siyi-designate
        label: "Track with pod"
        icon: crosshair
        order: 25
        designate: true
        config_key: track_designate
        config_value: true
        default_key: "t"
    parameters:
      - key: zoom
        binding: plugin.config
        schema: { type: number, minimum: 1, maximum: 30, step: 0.1, default: 1 }
        ui: { widget: range, label: "settings.zoom", order: 10 }
      - key: gimbal_mode
        binding: plugin.config
        schema: { type: string, enum: ["lock", "follow", "fpv"], default: "follow" }
        ui: { widget: enum, label: "settings.gimbalMode", order: 30 }
      - key: palette
        binding: plugin.config
        schema: { type: integer, minimum: 0, maximum: 8, default: 0 }
        ui: { widget: number, label: "settings.palette", order: 40 }
      - key: laser_enabled
        binding: plugin.config
        schema: { type: boolean, default: false }
        ui: { widget: boolean, label: "settings.laser", order: 60 }
`;

const FOLLOW_ME_MANIFEST = `schema_version: 2
id: com.altnautica.follow-me
name: "ADOS Follow-Me"
version: "0.2.4"
icon: "follow"
description: "Lock onto an operator-designated subject and fly a fixed-distance standoff follow from the companion."
description_long: |
  Click a subject in the live video and the drone follows it at a fixed
  distance and height. A generic person/object detector on the companion
  produces detections; the operator designates one; the companion locks onto
  that track and feeds the flight controller guided position setpoints.

  A lock-state safety gate stops commanding the instant the tracker reports the
  subject uncertain or lost, and never silently re-locks onto a different
  subject.
features:
  - "Click a detected subject in the cockpit and pick Follow to designate it"
  - "Fixed-distance, fixed-height standoff follow via guided setpoints"
  - "Lock-state safety gate: stops commanding on uncertain or lost"
  - "Optional gimbal point-at-subject when a gimbal is present"
hardware_requirements:
  cameras: "USB UVC or CSI camera bound to the vision pipeline"
  fc_firmware: "ArduPilot or PX4 in a guided position-hold mode"
  boards: ["cm4", "cm5", "rk3588s2", "rk3576", "rpi5"]
resource_impact:
  output_rate_hz: 6
  cpu_percent_peak: 25
  ram_mb: 128
  pids: 4
  startup_time_seconds: 3
telemetry_fields:
  - "follow.state"
documentation_url: "https://docs.altnautica.com/drone-agent/follow-me-overview"
homepage: "https://github.com/altnautica/ADOSExtensions/tree/main/extensions/follow-me"
author: "Altnautica"
license: "GPL-3.0-or-later"
risk: high
agent:
  runtime: python
  permissions:
    - id: vision.detection.subscribe
    - id: mavlink.read
    - id: mavlink.write
    - id: flight.guided_setpoint
    - id: event.publish
gcs:
  permissions:
    - id: ui.slot.flight-skill
    - id: ui.slot.node-detail-tab
  contributes:
    skills:
      - id: follow-me
        label: "Follow-Me"
        icon: "crosshair"
        category: behavior
        toggle: true
        confirm: true
        arm_requirement: armed
        default_binding: { key: "shift+f" }
        activation: { via: config, config_key: active }
        state: { via: event, topic: "follow.state" }
    target_actions:
      - id: follow
        label: "Follow this target"
        icon: crosshair
        order: 20
        applies_to_class: person
        designate: true
        config_key: active
        config_value: true
        default_key: "f"
      - id: stop-follow
        label: "Stop following"
        icon: circle-stop
        order: 21
        applies_to_class: person
        config_key: active
        config_value: false
        default_key: "x"
    tabs:
      - id: follow-me-tab
        slot: node.detail.tab
        profile: ["drone"]
        title: "Follow-Me"
        icon: "crosshair"
        order: 70
    parameters:
      - key: follow_distance_m
        binding: plugin.config
        schema: { type: number, minimum: 3, maximum: 30, step: 0.5, default: 8 }
        ui: { widget: range, label: "settings.followDistance", order: 10 }
      - key: follow_height_m
        binding: plugin.config
        schema: { type: number, minimum: 0, maximum: 20, step: 0.5, default: 4 }
        ui: { widget: range, label: "settings.followHeight", order: 20 }
      - key: gimbal_point
        binding: plugin.config
        schema: { type: boolean, default: true }
        ui: { widget: boolean, label: "settings.gimbalPoint", order: 30 }
`;

const BATTERY_MANIFEST = `schema_version: 2
id: com.altnautica.battery-health-panel
name: "ADOS Battery Health Panel"
version: "1.1.0"
icon: "battery"
description: "Cell-level battery diagnostics, predictive time-to-min, and anomaly alerts."
homepage: "https://github.com/altnautica/ADOSExtensions/tree/main/extensions/battery-health-panel"
author: "Altnautica"
license: "GPL-3.0-or-later"
risk: low
gcs:
  permissions:
    - id: ui.slot.node-detail-tab
    - id: ui.slot.notification-channel
    - id: telemetry.subscribe.battery
    - id: telemetry.subscribe.mavlink
    - id: recording.write
  contributes:
    tabs:
      - id: battery-health-tab
        slot: node.detail.tab
        profile: ["drone"]
        title: "Battery Health"
        icon: "battery"
        order: 30
    notifications:
      - id: battery-anomaly
        title: "Battery anomaly"
        severity: warning
`;

function row(
  overrides: Partial<RegistryPluginRow> & Pick<RegistryPluginRow, "plugin_id">,
): RegistryPluginRow {
  return {
    _id: `demo-${overrides.plugin_id}`,
    name: overrides.plugin_id,
    description: "",
    category: "drivers",
    license: "GPL-3.0-or-later",
    author_id: "altnautica",
    verified_publisher: true,
    latest_version: "0.0.0",
    tier: "first_party",
    ...overrides,
  };
}

/** The demo registry entries, in display order. */
export const DEMO_REGISTRY_ENTRIES: ReadonlyArray<DemoRegistryEntry> = [
  {
    row: row({
      plugin_id: "com.altnautica.siyi-pod",
      name: "ADOS SIYI Optical Pod",
      description:
        "Native driver for the SIYI optical-pod line: gimbal, zoom, thermal, laser rangefinder, and on-pod AI tracking.",
      category: "drivers",
      latest_version: "0.3.1",
      icon: "camera",
    }),
    manifestYaml: SIYI_MANIFEST,
    downloadUrl:
      "https://github.com/altnautica/ADOSExtensions/releases/download/siyi-pod-v0.3.1/siyi-pod.adosplug",
    archiveSha256:
      "0000000000000000000000000000000000000000000000000000000000000000",
    signerKeyId: "altnautica-2026-A",
  },
  {
    row: row({
      plugin_id: "com.altnautica.follow-me",
      name: "ADOS Follow-Me",
      description:
        "Lock onto an operator-designated subject and fly a fixed-distance standoff follow.",
      category: "ai",
      latest_version: "0.2.4",
      icon: "follow",
    }),
    manifestYaml: FOLLOW_ME_MANIFEST,
    downloadUrl:
      "https://github.com/altnautica/ADOSExtensions/releases/download/follow-me-v0.2.4/follow-me.adosplug",
    archiveSha256:
      "1111111111111111111111111111111111111111111111111111111111111111",
    signerKeyId: "altnautica-2026-A",
  },
  {
    row: row({
      plugin_id: "com.altnautica.battery-health-panel",
      name: "ADOS Battery Health Panel",
      description:
        "Cell-level battery diagnostics, predictive time-to-min, and anomaly alerts.",
      category: "telemetry",
      latest_version: "1.1.0",
      icon: "battery",
    }),
    manifestYaml: BATTERY_MANIFEST,
    downloadUrl:
      "https://github.com/altnautica/ADOSExtensions/releases/download/battery-health-panel-v1.1.0/battery-health-panel.adosplug",
    archiveSha256:
      "2222222222222222222222222222222222222222222222222222222222222222",
    signerKeyId: "altnautica-2026-A",
  },
];
