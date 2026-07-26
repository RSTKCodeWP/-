"use client";

import { useMemo } from "react";
import { useParamSafetyStore } from "@/stores/param-safety-store";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface DisconnectGuardProps {
  open: boolean;
  onCommitAndDisconnect: () => void;
  onDiscardAndDisconnect: () => void;
  onCancel: () => void;
}

export function DisconnectGuard({
  open,
  onCommitAndDisconnect,
  onDiscardAndDisconnect,
  onCancel,
}: DisconnectGuardProps) {
  const pendingWrites = useParamSafetyStore((s) => s.pendingWrites);
  const hasCritical = useParamSafetyStore((s) => s.hasCriticalPending());
  const isCriticalParam = useParamSafetyStore((s) => s.isCriticalParam);
  const pendingCount = pendingWrites.size;

  const entries = useMemo(
    () => Array.from(pendingWrites.values()),
    [pendingWrites],
  );

  if (!open || pendingCount === 0) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-bg-primary border border-border-default w-[460px] p-6 space-y-4">
        <div className="flex items-center gap-3">
          <AlertTriangle size={20} className="text-status-warning shrink-0" />
          <h2 className="text-sm font-semibold text-text-primary">Uncommitted Parameter Changes</h2>
        </div>

        <p className="text-xs text-text-secondary">
          {pendingCount} parameter{pendingCount !== 1 ? "s have" : " has"} been written to RAM but not committed to flash.
          Disconnecting now will lose these changes on next reboot.
        </p>

        {/* Pending writes table */}
        <div className="max-h-[200px] overflow-y-auto border border-border-default">
          <table className="w-full text-[10px]">
            <thead className="sticky top-0 bg-bg-secondary">
              <tr className="border-b border-border-default">
                <th className="px-2 py-1 text-left font-semibold text-text-secondary">Parameter</th>
                <th className="px-2 py-1 text-right font-semibold text-text-secondary">Old</th>
                <th className="px-2 py-1 text-center text-text-tertiary">{"\u2192"}</th>
                <th className="px-2 py-1 text-right font-semibold text-text-secondary">New</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => {
                const critical = isCriticalParam(entry.paramName);
                return (
                  <tr
                    key={entry.paramName}
                    className={cn(
                      "border-b border-border-default",
                      critical && "bg-status-error/5",
                    )}
                  >
                    <td className={cn(
                      "px-2 py-1 font-mono",
                      critical ? "text-status-error font-medium" : "text-text-primary",
                    )}>
                      {entry.paramName}
                    </td>
                    <td className="px-2 py-1 text-right font-mono text-text-tertiary">
                      {entry.oldValue}
                    </td>
                    <td className="px-2 py-1 text-center text-text-tertiary">{"\u2192"}</td>
                    <td className="px-2 py-1 text-right font-mono text-text-primary">
                      {entry.newValue}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {hasCritical && (
          <div className="p-2 bg-status-error/10 border border-status-error/20">
            <p className="text-[10px] text-status-error font-medium">
              Includes safety-critical parameters (failsafe, battery, motor, arming).
            </p>
          </div>
        )}

        <div className="flex items-center gap-2 pt-2">
          <Button variant="primary" size="sm" onClick={onCommitAndDisconnect}>
            Commit to Flash & Disconnect
          </Button>
          <Button variant="danger" size="sm" onClick={onDiscardAndDisconnect}>
            Discard & Disconnect
          </Button>
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}
