import { AppShell } from "../components/AppShell";
import { ContactDetailPanel } from "../components/ContactDetailPanel";
import { ContactList } from "../components/ContactList";
import { MapView } from "../components/MapView";
import { MissionLog } from "../components/MissionLog";
import { VideoPanel } from "../components/VideoPanel";
import { useSelectionStore } from "../store/selection";

/* OPS — the live instrument mode (DESIGN-SYSTEM §11.2). The original single-screen mission
 * control: map-primary, contact rail (with the detail panel above when something's selected),
 * docked video, mission-log foot drawer. The status strip + demo banner now live in the frame
 * (App), so this page owns only the region right of the console rail. Everything still reads
 * the SAME global stores, so the selection spine is shared with REVIEW/MAP. */

export function OpsPage() {
  const hasSelection = useSelectionStore((s) => s.selectedId !== null);

  return (
    <div data-testid="page-ops" className="h-full">
      <AppShell
        map={<MapView />}
        list={
          <div className="flex h-full flex-col">
            {hasSelection && (
              <div className="border-b border-hairline bg-surface-1">
                <ContactDetailPanel />
              </div>
            )}
            <div className="min-h-0 flex-1 overflow-auto">
              <ContactList />
            </div>
          </div>
        }
        video={<VideoPanel />}
        missionLog={<MissionLog />}
      />
    </div>
  );
}
