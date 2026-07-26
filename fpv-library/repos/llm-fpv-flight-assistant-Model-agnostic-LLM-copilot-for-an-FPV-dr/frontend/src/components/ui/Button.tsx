import { theme } from "../../theme";
type V = "default" | "accent" | "danger";
const bg: Record<V, string> = { default: "#16202e", accent: theme.color.accent, danger: theme.color.danger };
export function Button({ children, onClick, variant = "default", title }:
  { children: React.ReactNode; onClick?: () => void; variant?: V; title?: string }) {
  return <button onClick={onClick} title={title} style={{
    padding: "8px 12px", border: `1px solid ${theme.color.border}`, borderRadius: theme.radius.sm,
    background: bg[variant], color: variant === "accent" ? "#04130b" : theme.color.text,
    font: `700 12px ${theme.font.ui}`, cursor: "pointer" }}>{children}</button>;
}
