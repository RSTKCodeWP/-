export const theme = {
  color: { bg: "#05080d", panel: "rgba(13,18,28,0.82)", border: "#1f2a3a",
           text: "#e6edf3", dim: "#8b9bb0", accent: "#3ddc97", warn: "#f5b945",
           danger: "#ff4d4f", ok: "#3ddc97", lost: "#6b7787" },
  radius: { sm: 6, md: 10, lg: 16 },
  space: (n: number) => n * 4,
  font: { ui: "Inter, system-ui, sans-serif", mono: "'JetBrains Mono', ui-monospace, monospace" },
  z: { video: 0, osd: 10, hud: 20, panel: 30, modal: 40 },
} as const;
export type Status = "ok" | "warn" | "lost";
