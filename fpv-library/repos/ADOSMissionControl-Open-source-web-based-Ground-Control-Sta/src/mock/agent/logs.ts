// Exempt from 300 LOC soft rule: pure mock log fixture.
/**
 * @module mock/agent/logs
 * @description Mock service log entries replayed by the demo agent.
 * Cached on first import so successive `/api/logs` calls return the
 * same timeline.
 * @license GPL-3.0-only
 */

import type { LogEntry } from "@/lib/agent/types";

function generateMockLogs(): LogEntry[] {
  const now = new Date();
  const entries: LogEntry[] = [];
  const bootMessages: [string, string, LogEntry["level"]][] = [
    ["agent", "ADOS Drone Agent v0.1.0 starting", "info"],
    ["agent", "Board: Raspberry Pi CM4 (4GB)", "info"],
    ["agent", "OS: Raspberry Pi OS Lite (Bookworm)", "info"],
    ["mavlink-proxy", "Connecting to FC on /dev/ttyAMA0 @ 921600", "info"],
    ["mavlink-proxy", "Heartbeat received: ArduCopter 4.5.7", "info"],
    ["mavlink-proxy", "Parameter sync complete: 1042 params", "info"],
    ["video-pipeline", "WFB-ng initializing on wlan1", "info"],
    ["video-pipeline", "TX power: 29 dBm, channel: 165 (5825 MHz)", "info"],
    ["video-pipeline", "Video pipeline active: 1280x720@30fps H.264", "info"],
    ["mqtt-gateway", "Connecting to mqtt://fleet.altnautica.com:8883", "info"],
    ["mqtt-gateway", "TLS handshake complete, authenticated", "info"],
    ["mqtt-gateway", "Subscribed to fleet/alpha-1/cmd/#", "info"],
    ["suite-runtime", "Loading suite: Sentry — Security Patrol", "info"],
    ["suite-runtime", "Suite manifest validated, 3 sensors required", "info"],
    ["sensor-manager", "Discovered 5 sensors on I2C-1, UART-2, UART-3, SPI-0", "info"],
    ["sensor-manager", "BME280 barometer OK @ 50 Hz", "info"],
    ["sensor-manager", "MPU6050 IMU OK @ 1000 Hz", "info"],
    ["sensor-manager", "BN-880 GPS OK @ 10 Hz, 3D fix", "info"],
    ["sensor-manager", "TFMini-S rangefinder OK @ 100 Hz", "info"],
    ["sensor-manager", "PMW3901 optical flow — quality low (142/255)", "warning"],
    ["script-executor", "Command interface ready on :8080", "info"],
    ["agent", "All services started, uptime monitoring active", "info"],
    ["mavlink-proxy", "Mode changed: STABILIZE -> AUTO", "info"],
    ["mavlink-proxy", "Vehicle armed", "info"],
    ["suite-runtime", "Mission started: patrol_grid_01", "info"],
    ["mqtt-gateway", "Telemetry publishing at 2 Hz", "info"],
    ["sensor-manager", "Rangefinder AGL: 50.2 m", "info"],
    ["video-pipeline", "Stream bitrate: 4.2 Mbps, latency: 42ms", "info"],
    ["mavlink-proxy", "Waypoint 3/12 reached", "info"],
    ["suite-runtime", "Sentry alert: motion detected sector B-4", "warning"],
    ["mqtt-gateway", "Alert published to fleet/alpha-1/alerts", "info"],
    ["agent", "System temp: 45.2C (normal)", "info"],
    ["agent", "CPU: 34%, RAM: 1.2 GB / 4.0 GB", "info"],
    ["mavlink-proxy", "Waypoint 6/12 reached", "info"],
    ["video-pipeline", "Recording: 00:14:32, 3.8 GB", "info"],
    ["sensor-manager", "PMW3901 quality improved (198/255)", "info"],
    ["mavlink-proxy", "Waypoint 9/12 reached", "info"],
    ["mqtt-gateway", "Messages sent: 14832, received: 9217", "info"],
    ["agent", "Battery: 82%, estimated remaining: 18 min", "info"],
  ];

  bootMessages.forEach(([service, message, level], i) => {
    const ts = new Date(now.getTime() - (bootMessages.length - i) * 2000);
    entries.push({ timestamp: ts.toISOString(), level, service, message });
  });

  return entries;
}

export const MOCK_LOGS: LogEntry[] = generateMockLogs();
