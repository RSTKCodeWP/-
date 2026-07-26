"use client";

import { useState, useEffect, useRef } from "react";
import { useDroneStore } from "@/stores/drone-store";
import { Button } from "@/components/ui/button";

export function CalibrationRebootBanner({
  label,
  onReboot,
}: {
  label: string;
  onReboot: () => void;
}) {
  const [dismissed, setDismissed] = useState(false);
  const [fadingOut, setFadingOut] = useState(false);
  const lastHeartbeat = useDroneStore((s) => s.lastHeartbeat);
  const prevHeartbeatRef = useRef(lastHeartbeat);
  const rebootDetectedRef = useRef(false);

  // Detect reboot: heartbeat gap > 2s then resume
  useEffect(() => {
    if (dismissed) return;

    const prev = prevHeartbeatRef.current;
    prevHeartbeatRef.current = lastHeartbeat;

    if (prev === 0 || lastHeartbeat === 0) return;

    const gap = lastHeartbeat - prev;
    if (gap > 2000 && !rebootDetectedRef.current) {
      rebootDetectedRef.current = true;
      const timer = setTimeout(() => {
        setFadingOut(true);
        const fadeTimer = setTimeout(() => setDismissed(true), 400);
        return () => clearTimeout(fadeTimer);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [lastHeartbeat, dismissed]);

  if (dismissed) return null;

  return (
    <div
      className="flex items-center justify-between gap-3 border border-status-warning/30 bg-status-warning/10 px-4 py-3 transition-all"
      style={fadingOut ? { animation: "fade-out-down 0.4s ease-out forwards" } : undefined}
    >
      <div>
        <p className="text-sm font-medium text-status-warning">Reboot Required</p>
        <p className="text-xs text-text-secondary mt-0.5">
          {label}. Reboot the flight controller to apply.
        </p>
      </div>
      <Button variant="primary" size="sm" onClick={onReboot}>
        Reboot FC
      </Button>
    </div>
  );
}
