"use client";

import { AlertTriangle, AlertCircle, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/utils";
import type { Alert } from "@/lib/types";

interface AlertRowProps {
  alert: Alert;
  onAcknowledge?: (id: string) => void;
}

const severityIcons = {
  critical: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const severityColors = {
  critical: "text-status-error",
  warning: "text-status-warning",
  info: "text-accent-primary",
};

export function AlertRow({ alert, onAcknowledge }: AlertRowProps) {
  const Icon = severityIcons[alert.severity];

  return (
    <div
      className={cn(
        "flex items-center gap-2 px-2 py-1.5 border-b border-border-default text-xs",
        alert.acknowledged && "opacity-50"
      )}
    >
      <Icon size={14} className={severityColors[alert.severity]} />
      <span className="text-text-tertiary font-mono tabular-nums shrink-0">
        {formatTime(alert.timestamp)}
      </span>
      <span className="text-accent-primary font-semibold shrink-0">{alert.droneName}</span>
      <span className="text-text-secondary flex-1 truncate">{alert.message}</span>
      {!alert.acknowledged && onAcknowledge && (
        <button
          onClick={() => onAcknowledge(alert.id)}
          className="text-[10px] text-text-tertiary hover:text-text-primary uppercase tracking-wider px-1.5 py-0.5 border border-border-default hover:border-border-strong transition-colors cursor-pointer"
        >
          ACK
        </button>
      )}
    </div>
  );
}
