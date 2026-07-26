import { useEffect, useState } from "react";
import { theme } from "../theme";
import { Panel } from "./ui/Panel";

const ROWS: string[][] = [
  ["q", "w", "e"],
  ["a", "s", "d"],
  ["r", "f", "shift"],
];
const LABEL: Record<string, string> = {
  q: "Q ⟲", w: "W ▲", e: "E ⟳", a: "A ◀", s: "S ▼", d: "D ▶",
  r: "R ⤒", f: "F ⤓", shift: "⇧ boost",
};

export function ManualHUD({ keys }: { keys: React.MutableRefObject<Set<string>> }) {
  const [pressed, setPressed] = useState<string[]>([]);
  useEffect(() => {
    const id = setInterval(() => setPressed([...keys.current]), 80);
    return () => clearInterval(id);
  }, [keys]);
  const active = new Set(pressed);
  return (
    <Panel style={{ padding: 10 }}>
      <div style={{ fontSize: 10, color: theme.color.dim, marginBottom: 6, letterSpacing: 0.5 }}>
        MANUAL — you have control · WASD move · Q/E yaw · R/F alt · Shift boost
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4, alignItems: "center" }}>
        {ROWS.map((row, ri) => (
          <div key={ri} style={{ display: "flex", gap: 4 }}>
            {row.map((k) => (
              <span key={k} style={{
                minWidth: 54, textAlign: "center", padding: "5px 7px",
                fontFamily: theme.font.mono, fontSize: 11,
                borderRadius: theme.radius.sm,
                border: `1px solid ${active.has(k) ? theme.color.accent : theme.color.border}`,
                background: active.has(k) ? theme.color.accent : "#0f1a26",
                color: active.has(k) ? "#04130b" : theme.color.text,
              }}>{LABEL[k]}</span>
            ))}
          </div>
        ))}
      </div>
    </Panel>
  );
}
