import type { Telemetry } from "../../types";
import { Crosshair } from "./Crosshair";
import { AttitudeIndicator } from "./AttitudeIndicator";
import { CompassTape } from "./CompassTape";
import { Ladder } from "./Ladder";
export function OsdOverlay({ t }: { t: Telemetry | null }) {
  if (!t) return <Crosshair />;
  return (<div style={{ position: "absolute", inset: 0, zIndex: 10, pointerEvents: "none" }}>
    <AttitudeIndicator roll={t.roll ?? 0} pitch={t.pitch ?? 0} />
    <Crosshair />
    <CompassTape heading={t.yaw ?? 0} />
    <Ladder value={t.alt_m} step={5} span={40} unit="ALT m" side="left" />
    <Ladder value={t.speed_ms} step={2} span={16} unit="SPD m/s" side="right" />
  </div>);
}
