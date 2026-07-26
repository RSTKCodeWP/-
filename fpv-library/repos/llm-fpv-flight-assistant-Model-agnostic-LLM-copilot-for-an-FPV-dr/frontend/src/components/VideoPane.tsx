import type { Telemetry, VideoStatus } from "../types";
import { FallbackScene } from "./FallbackScene";

export function VideoPane({ videoStatus, telemetry }:
  { videoStatus: VideoStatus | null; telemetry: Telemetry | null }) {
  const box: React.CSSProperties = {
    position: "absolute", inset: 0, width: "100%", height: "100%", background: "#000", overflow: "hidden",
  };
  const tag = (label: string) => (
    <span style={{ position: "absolute", top: 8, left: 8, fontSize: 11,
                   background: "rgba(0,0,0,.6)", padding: "2px 8px", borderRadius: 10 }}>{label}</span>
  );
  if (videoStatus?.ok) {
    return (
      <div style={box}>
        <img src={videoStatus.url} alt="FPV video"
             style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        {tag("LIVE · gz camera")}
      </div>
    );
  }
  return (
    <div style={box}>
      <FallbackScene t={telemetry} />
      {tag("SIMULATED · telemetry scene")}
    </div>
  );
}
