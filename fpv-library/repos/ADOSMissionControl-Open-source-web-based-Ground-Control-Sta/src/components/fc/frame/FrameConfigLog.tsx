"use client";

import { useRef, useEffect } from "react";
import { Trash2 } from "lucide-react";
import React from "react";

export interface ConfigLogEntry {
  id: number;
  timestamp: number;
  type: "read" | "write" | "flash" | "error" | "info";
  message: string;
}

const LOG_TYPE_COLORS: Record<ConfigLogEntry["type"], string> = {
  read: "text-accent-primary",
  write: "text-accent-secondary",
  flash: "text-status-success",
  error: "text-status-error",
  info: "text-text-tertiary",
};

interface FrameConfigLogProps {
  logEntries: ConfigLogEntry[];
  onClear: () => void;
}

export function FrameConfigLog({ logEntries, onClear }: FrameConfigLogProps) {
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logEntries.length]);

  return (
    <div className="w-[280px] shrink-0 border-l border-border-default bg-bg-secondary overflow-hidden flex-col hidden xl:flex">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border-default">
        <h3 className="text-xs font-medium text-text-primary">Config Log</h3>
        <button
          onClick={onClear}
          className="p-1 text-text-tertiary hover:text-text-secondary transition-colors"
          title="Clear log"
        >
          <Trash2 size={12} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-2 font-mono text-[10px] space-y-0.5">
        {logEntries.length === 0 ? (
          <p className="text-text-tertiary text-center py-4">No events yet. Read from FC to start.</p>
        ) : (
          logEntries.map((entry) => (
            <div key={entry.id} className="flex gap-1.5 leading-relaxed">
              <span className="text-text-tertiary shrink-0">
                {new Date(entry.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
              <span className={LOG_TYPE_COLORS[entry.type]}>{entry.message}</span>
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}

export function FrameCard({
  icon,
  title,
  description,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-border-default bg-bg-secondary p-4 space-y-3">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-accent-primary">{icon}</span>
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-medium text-text-primary">{title}</h2>
          <p className="text-[10px] text-text-tertiary">{description}</p>
        </div>
      </div>
      {children}
    </div>
  );
}
