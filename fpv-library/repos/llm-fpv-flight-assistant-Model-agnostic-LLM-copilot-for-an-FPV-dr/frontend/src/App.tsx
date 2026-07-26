import { useDashboardSocket } from "./useDashboardSocket";
import { useManualControl } from "./useManualControl";
import { VideoPane } from "./components/VideoPane";
import { OsdOverlay } from "./components/osd/OsdOverlay";
import { TopBar } from "./components/TopBar";
import { QuickActions } from "./components/QuickActions";
import { ChatDrawer } from "./components/ChatDrawer";
import { ManualHUD } from "./components/ManualHUD";
import { EventLog } from "./components/EventLog";
import { theme } from "./theme";

const WS_URL = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";
const MAX_SPEED = 12;

export function App() {
  const d = useDashboardSocket(WS_URL);
  const keys = useManualControl(d.control === "manual", MAX_SPEED, d.sendManual);
  return (
    <div style={{ position: "fixed", inset: 0, background: theme.color.bg, color: theme.color.text,
                  fontFamily: theme.font.ui, overflow: "hidden" }}>
      <VideoPane videoStatus={d.videoStatus} telemetry={d.telemetry} />
      <OsdOverlay t={d.telemetry} />
      <TopBar connected={d.connected} telemetry={d.telemetry} video={d.videoStatus}
        control={d.control} onTake={d.takeControl} onRelease={d.release} onAbort={d.abort} />
      <div style={{ position: "absolute", left: 12, bottom: 12, zIndex: theme.z.panel }}>
        <QuickActions quick={d.quick} />
      </div>
      {d.control === "manual" && (
        <div style={{ position: "absolute", left: "50%", bottom: 12, transform: "translateX(-50%)", zIndex: theme.z.panel }}>
          <ManualHUD keys={keys} />
        </div>
      )}
      <div style={{ position: "absolute", right: 12, bottom: 12, width: 360, zIndex: theme.z.panel }}>
        <ChatDrawer chat={d.chat} proposal={d.proposal}
          onChat={d.sendChat} onConfirm={d.confirm} onCancel={d.cancel} />
      </div>
      <div style={{ position: "absolute", left: 12, top: 56, zIndex: theme.z.panel }}>
        <EventLog events={d.events} />
      </div>
    </div>
  );
}
