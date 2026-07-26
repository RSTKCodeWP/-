// Exempt from 300 LOC soft rule: pure mock fixture data.
/**
 * @module mock/agent/peripherals
 * @description Mock peripheral device list returned by the demo agent.
 * @license GPL-3.0-only
 */

import type { PeripheralInfo } from "@/lib/agent/types";

export const MOCK_PERIPHERALS: PeripheralInfo[] = [
  { name: "BME280", type: "barometer", category: "sensor", bus: "I2C-1", address: "0x76", rate_hz: 50, status: "ok", last_reading: "101325 Pa / 24.3C" },
  { name: "MPU6050", type: "imu", category: "sensor", bus: "I2C-1", address: "0x68", rate_hz: 1000, status: "ok", last_reading: "ax=0.02 ay=-0.01 az=9.81" },
  { name: "BN-880", type: "gps", category: "sensor", bus: "UART-2", address: "115200", rate_hz: 10, status: "ok", last_reading: "3D Fix, 17 sats, HDOP 0.8" },
  { name: "TFMini-S", type: "rangefinder", category: "sensor", bus: "UART-3", address: "115200", rate_hz: 100, status: "ok", last_reading: "2.34 m" },
  { name: "PMW3901", type: "optical_flow", category: "sensor", bus: "SPI-0", address: "CS0", rate_hz: 80, status: "warning", last_reading: "dx=12 dy=-3 quality=142" },
  { name: "Pi Camera v3", type: "camera", category: "camera", bus: "CSI-0", address: "N/A", rate_hz: 30, status: "ok", last_reading: "1920x1080 @ 30fps H.264" },
  { name: "RTL8812EU", type: "video_tx", category: "video", bus: "USB-C", address: "wlan1", rate_hz: 0, status: "ok", last_reading: "29 dBm, ch165 (5825 MHz), 4.2 Mbps" },
  { name: "SimpleBGC", type: "gimbal_controller", category: "gimbal", bus: "UART-4", address: "115200", rate_hz: 50, status: "ok", last_reading: "pitch=-15.2 roll=0.3 yaw=142.8" },
];
