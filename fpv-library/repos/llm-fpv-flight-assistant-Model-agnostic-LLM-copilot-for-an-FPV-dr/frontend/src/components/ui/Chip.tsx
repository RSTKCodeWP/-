import { theme, type Status } from "../../theme";
const dot: Record<Status, string> = { ok: theme.color.ok, warn: theme.color.warn, lost: theme.color.lost };
export function Chip({ label, value, status = "ok" }: { label: string; value?: string; status?: Status }) {
  return (
    <div style={{ display: "inline-flex", gap: 6, alignItems: "center", padding: "4px 9px",
      background: theme.color.panel, border: `1px solid ${theme.color.border}`,
      borderRadius: theme.radius.sm, font: `600 11px ${theme.font.ui}`, color: theme.color.text }}>
      <span style={{ width: 7, height: 7, borderRadius: 7, background: dot[status] }} />
      <span style={{ color: theme.color.dim, letterSpacing: 0.5 }}>{label}</span>
      {value && <span style={{ fontFamily: theme.font.mono }}>{value}</span>}
    </div>
  );
}
