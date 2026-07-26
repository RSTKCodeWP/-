"use client";

/**
 * @module history/detail/charts/custom-chart/TracePicker
 * @description Two-step picker for adding a new trace to the custom
 * chart. Operator first picks a channel, then picks a field within
 * that channel.
 * @license GPL-3.0-only
 */

import { useState } from "react";
import { X } from "lucide-react";
import type { ChannelDef } from "./types";

export interface TracePickerProps {
  channels: ChannelDef[];
  onPick: (channel: string, field: string) => void;
  onCancel: () => void;
}

export function TracePicker({ channels, onPick, onCancel }: TracePickerProps) {
  const [selectedChannel, setSelectedChannel] = useState<string | null>(null);
  const chanDef = channels.find((c) => c.channel === selectedChannel);

  return (
    <div className="border border-border-default rounded p-2 mb-2 bg-bg-tertiary">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] font-semibold text-text-secondary uppercase tracking-wider">
          {selectedChannel ? "Pick field" : "Pick channel"}
        </span>
        <button onClick={onCancel} className="text-text-tertiary hover:text-text-primary">
          <X size={12} />
        </button>
      </div>
      {!selectedChannel ? (
        <div className="flex flex-wrap gap-1">
          {channels.map((c) => (
            <button
              key={c.channel}
              onClick={() => setSelectedChannel(c.channel)}
              className="text-[10px] px-2 py-1 rounded bg-bg-secondary text-text-primary hover:bg-accent-primary/20 transition-colors"
            >
              {c.label}
            </button>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          <button
            onClick={() => setSelectedChannel(null)}
            className="text-[9px] text-accent-primary hover:underline self-start mb-0.5"
          >
            ← Back to channels
          </button>
          <div className="flex flex-wrap gap-1">
            {chanDef?.fields.map((f) => (
              <button
                key={f.key}
                onClick={() => onPick(selectedChannel, f.key)}
                className="text-[10px] px-2 py-1 rounded bg-bg-secondary text-text-primary hover:bg-accent-primary/20 transition-colors"
              >
                {f.label}
                {f.unit && <span className="text-text-tertiary ml-0.5">({f.unit})</span>}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
