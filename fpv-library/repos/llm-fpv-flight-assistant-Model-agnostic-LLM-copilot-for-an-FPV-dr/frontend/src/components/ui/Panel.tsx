import { theme } from "../../theme";
export function Panel({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return <div style={{ background: theme.color.panel, border: `1px solid ${theme.color.border}`,
    borderRadius: theme.radius.md, backdropFilter: "blur(6px)", ...style }}>{children}</div>;
}
