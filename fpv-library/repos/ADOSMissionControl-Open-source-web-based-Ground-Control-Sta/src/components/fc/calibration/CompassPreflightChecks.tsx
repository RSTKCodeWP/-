"use client";

import { useToast } from "@/components/ui/toast";
import { useDroneManager } from "@/stores/drone-manager";
import { cn } from "@/lib/utils";

interface CompassPreflightChecksProps {
  compassParams: {
    COMPASS_USE: number | null;
    COMPASS_ORIENT: number | null;
    COMPASS_AUTO_ROT: number | null;
    COMPASS_OFFS_MAX: number | null;
    COMPASS_LEARN: number | null;
    COMPASS_EXTERNAL: number | null;
  };
  setCompassParams: React.Dispatch<React.SetStateAction<{
    COMPASS_USE: number | null;
    COMPASS_ORIENT: number | null;
    COMPASS_AUTO_ROT: number | null;
    COMPASS_OFFS_MAX: number | null;
    COMPASS_LEARN: number | null;
    COMPASS_EXTERNAL: number | null;
  }>>;
}

export function CompassPreflightChecks({ compassParams, setCompassParams }: CompassPreflightChecksProps) {
  const getSelectedProtocol = useDroneManager((s) => s.getSelectedProtocol);
  const { toast } = useToast();

  return (
    <div className="border border-border-default bg-bg-secondary p-4">
      <h3 className="text-xs font-medium text-text-primary mb-2">Compass Pre-flight Checks</h3>
      <div className="space-y-1.5">
        {/* COMPASS_USE */}
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-text-secondary font-mono">COMPASS_USE</span>
          {compassParams.COMPASS_USE === null ? (
            <span className="text-text-tertiary">Loading...</span>
          ) : compassParams.COMPASS_USE === 1 ? (
            <span className="text-status-success font-mono">Enabled</span>
          ) : (
            <span className="text-status-error font-mono">Disabled — enable COMPASS_USE first</span>
          )}
        </div>
        {/* COMPASS_ORIENT */}
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-text-secondary font-mono">COMPASS_ORIENT</span>
          {compassParams.COMPASS_ORIENT === null ? (
            <span className="text-text-tertiary">Loading...</span>
          ) : (
            <span className="text-text-primary font-mono">
              {compassParams.COMPASS_ORIENT} {compassParams.COMPASS_ORIENT === 0 ? "(None)" : compassParams.COMPASS_ORIENT === 6 ? "(Yaw270)" : ""}
            </span>
          )}
        </div>
        {/* COMPASS_AUTO_ROT */}
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-text-secondary font-mono">COMPASS_AUTO_ROT</span>
          {compassParams.COMPASS_AUTO_ROT === null ? (
            <span className="text-text-tertiary">Loading...</span>
          ) : compassParams.COMPASS_AUTO_ROT === 3 ? (
            <span className="text-status-success font-mono">3 (Lenient)</span>
          ) : (
            <span className="flex items-center gap-2">
              <span className="text-status-warning font-mono">{compassParams.COMPASS_AUTO_ROT} — recommend 3 for lenient orientation detection</span>
              <button
                className="text-[9px] text-accent-primary hover:underline"
                onClick={async () => {
                  const protocol = getSelectedProtocol();
                  if (!protocol) return;
                  await protocol.setParameter("COMPASS_AUTO_ROT", 3);
                  setCompassParams((p) => ({ ...p, COMPASS_AUTO_ROT: 3 }));
                  toast("COMPASS_AUTO_ROT set to 3", "success");
                }}
              >
                Fix
              </button>
            </span>
          )}
        </div>
        {/* COMPASS_OFFS_MAX */}
        {compassParams.COMPASS_OFFS_MAX !== null && (
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-text-secondary font-mono">COMPASS_OFFS_MAX</span>
            <span className="flex items-center gap-2">
              <span className={cn("font-mono", compassParams.COMPASS_OFFS_MAX < 850 ? "text-status-warning" : "text-text-primary")}>
                {compassParams.COMPASS_OFFS_MAX} {compassParams.COMPASS_OFFS_MAX < 850 ? "— low limit" : ""}
              </span>
              {compassParams.COMPASS_OFFS_MAX < 2000 && (
                <button
                  className="text-[9px] text-accent-primary hover:underline"
                  onClick={async () => {
                    const protocol = getSelectedProtocol();
                    if (!protocol) return;
                    await protocol.setParameter("COMPASS_OFFS_MAX", 2000);
                    setCompassParams((p) => ({ ...p, COMPASS_OFFS_MAX: 2000 }));
                    toast("COMPASS_OFFS_MAX set to 2000", "success");
                  }}
                >
                  Increase to 2000
                </button>
              )}
            </span>
          </div>
        )}
        {/* COMPASS_LEARN */}
        {compassParams.COMPASS_LEARN !== null && (
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-text-secondary font-mono">COMPASS_LEARN</span>
            <span className="text-text-primary font-mono">
              {compassParams.COMPASS_LEARN} ({compassParams.COMPASS_LEARN === 0 ? "Off" : compassParams.COMPASS_LEARN === 1 ? "Internal" : compassParams.COMPASS_LEARN === 2 ? "EKF" : compassParams.COMPASS_LEARN === 3 ? "InFlight" : "Unknown"})
            </span>
          </div>
        )}
        {/* COMPASS_EXTERNAL */}
        {compassParams.COMPASS_EXTERNAL !== null && (
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-text-secondary font-mono">COMPASS_EXTERNAL</span>
            <span className="text-text-primary font-mono">
              {compassParams.COMPASS_EXTERNAL === 1 ? "External" : "Internal"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
