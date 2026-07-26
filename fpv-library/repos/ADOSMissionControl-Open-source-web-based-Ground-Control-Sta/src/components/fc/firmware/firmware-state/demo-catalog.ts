// Exempt from 300 LOC soft rule: self-contained demo-mode catalog data.
/**
 * @module fc/firmware/firmware-state/demo-catalog
 * @description Demo-mode catalog for the ADOS agent picker. Mirrors a
 * small slice of the embedded fallback in `/api/ados-manifest` so the
 * Flash Tool stays usable when demo mode is active and the proxy may
 * not be reachable. Consumed only inside the demo-mode branch of the
 * ADOS-agent loader (never imported in production code paths).
 * @license GPL-3.0-only
 */

import type { AdosAgentBoard } from "@/lib/protocol/firmware/ados-agent-manifest";

export const DEMO_ADOS_AGENT_VERSION = "v0.1.0";

const DEMO_FULL_INSTALL_CMD =
  "curl -sSL https://github.com/altnautica/ADOSDroneAgent/releases/latest/download/install.sh | sudo bash";
const DEMO_FULL_INSTALL_GROUND_CMD =
  "curl -sSL https://github.com/altnautica/ADOSDroneAgent/releases/latest/download/install.sh | sudo bash -s -- --profile ground-station";

export const DEMO_ADOS_BOARDS: AdosAgentBoard[] = [
  {
    id: "pi-zero-2w",
    label: "Raspberry Pi Zero 2 W",
    soc: "BCM2710A1",
    arch: "aarch64-glibc",
    stacks: ["ados-drone-agent"],
    description: "512 MB LPDDR2, microSD boot, mainline Wi-Fi.",
    installs: {
      "ados-drone-agent": {
        method: "curl",
        command: DEMO_FULL_INSTALL_CMD,
        notes: [
          "Run on a Pi already booted into Raspberry Pi OS Lite.",
          "Connect to your Wi-Fi network before running the command.",
        ],
      },
    },
  },
  {
    id: "rpi4b",
    label: "Raspberry Pi 4B",
    soc: "BCM2711",
    arch: "aarch64-glibc",
    stacks: ["ados-drone-agent", "ados-ground-agent"],
    description: "1-8 GB RAM, microSD boot.",
    installs: {
      "ados-drone-agent": {
        method: "curl",
        command: DEMO_FULL_INSTALL_CMD,
        notes: ["Run on a Pi already booted into Raspberry Pi OS."],
      },
      "ados-ground-agent": {
        method: "curl",
        command: DEMO_FULL_INSTALL_GROUND_CMD,
        notes: [
          "Run on a Pi already booted into Raspberry Pi OS.",
          "Plug in your RTL8812EU adapter, OLED display, and buttons before running the installer if you want them auto-detected.",
        ],
      },
    },
  },
  {
    id: "rk3566",
    label: "Radxa CM3 (RK3566)",
    soc: "RK3566",
    arch: "aarch64-glibc",
    stacks: ["ados-drone-agent", "ados-ground-agent"],
    description: "2-8 GB RAM, eMMC + microSD options.",
    installs: {
      "ados-drone-agent": {
        method: "curl",
        command: DEMO_FULL_INSTALL_CMD,
        notes: ["Run on a CM3 booted into Radxa OS."],
      },
      "ados-ground-agent": {
        method: "curl",
        command: DEMO_FULL_INSTALL_GROUND_CMD,
        notes: ["Run on a CM3 booted into Radxa OS."],
      },
    },
  },
];
