import type { Telemetry, VideoStatus } from "../types";
import { Chip } from "./ui/Chip";
export function HealthChips({ connected, telemetry, video }:
  { connected: boolean; telemetry: Telemetry | null; video: VideoStatus | null }) {
  const batt = telemetry ? Math.round(telemetry.battery_pct * 100) : null;
  return (<div style={{ display: "flex", gap: 8 }}>
    <Chip label="LINK" status={connected ? "ok" : "lost"} value={connected ? "up" : "down"} />
    <Chip label="VIDEO" status={video?.ok ? "ok" : "lost"} value={video?.ok ? "live" : "—"} />
    <Chip label="GPS/EKF" status={telemetry ? (telemetry.gps_ok && telemetry.ekf_ok ? "ok" : "warn") : "lost"}
      value={telemetry ? `${telemetry.gps_ok ? "ok" : "no"}/${telemetry.ekf_ok ? "ok" : "no"}` : "—"} />
    <Chip label="BATT" status={batt == null ? "lost" : batt < 20 ? "warn" : "ok"} value={batt == null ? "—" : `${batt}%`} />
  </div>);
}
