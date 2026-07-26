import { useState } from "react";
import type { EventEntry } from "../types";
import { theme } from "../theme";
import { Panel } from "./ui/Panel";

const KIND_COLOR: Record<string, string> = {
  result: theme.color.accent, control: theme.color.warn,
  proposal: theme.color.text, narration: theme.color.dim,
};

function hhmmss(ts: number): string {
  return new Date(ts).toTimeString().slice(0, 8);
}

export function EventLog({ events }: { events: EventEntry[] }) {
  const [open, setOpen] = useState(true);
  const ordered = [...events].reverse(); // newest first
  return (
    <Panel style={{ width: 280, maxHeight: "40vh", display: "flex", flexDirection: "column" }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "7px 10px", background: "transparent", border: "none",
          color: theme.color.dim, font: `700 11px ${theme.font.ui}`, letterSpacing: 0.5,
          cursor: "pointer" }}>
        <span>EVENTS ({events.length})</span><span>{open ? "▾" : "▸"}</span>
      </button>
      {open ? (
        <ul style={{ listStyle: "none", margin: 0, padding: "0 10px 10px",
          overflowY: "auto", display: "flex", flexDirection: "column", gap: 3 }}>
          {ordered.map((e, i) => (
            <li key={i} style={{ display: "flex", gap: 6, fontSize: 11, lineHeight: 1.4 }}>
              <span style={{ color: theme.color.dim, fontFamily: theme.font.mono }}>{hhmmss(e.ts)}</span>
              <span style={{ color: KIND_COLOR[e.kind] || theme.color.text }}>{e.text}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </Panel>
  );
}
