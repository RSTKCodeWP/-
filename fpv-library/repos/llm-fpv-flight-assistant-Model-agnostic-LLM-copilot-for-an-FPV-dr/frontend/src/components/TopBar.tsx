import type { Telemetry, VideoStatus, ControlWho } from "../types";
import { theme } from "../theme";
import { HealthChips } from "./HealthChips";
import { ControlToggle } from "./ControlToggle";
import { AbortButton } from "./AbortButton";
export function TopBar({ connected, telemetry, video, control, onTake, onRelease, onAbort }: {
  connected: boolean; telemetry: Telemetry | null; video: VideoStatus | null;
  control: ControlWho; onTake: () => void; onRelease: () => void; onAbort: () => void;
}) {
  return (
    <div style={{ position: "absolute", top: 0, left: 0, right: 0, zIndex: theme.z.hud,
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "10px 14px", gap: 12,
      background: "linear-gradient(180deg, rgba(5,8,13,0.85), rgba(5,8,13,0))" }}>
      <HealthChips connected={connected} telemetry={telemetry} video={video} />
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <ControlToggle control={control} onTake={onTake} onRelease={onRelease} />
        <AbortButton onAbort={onAbort} />
      </div>
    </div>
  );
}
