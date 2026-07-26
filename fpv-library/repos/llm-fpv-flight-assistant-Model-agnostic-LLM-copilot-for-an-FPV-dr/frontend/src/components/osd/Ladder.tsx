import { ladderTicks } from "../../osd/math";
export function Ladder({ value, step, span, unit, side }:
  { value: number; step: number; span: number; unit: string; side: "left" | "right" }) {
  const ticks = ladderTicks(value, step, span);
  const anchor = side === "left" ? "start" : "end";
  return (<svg style={{ position: "absolute", [side]: 10, top: "50%", transform: "translateY(-50%)", width: 70, height: 220, pointerEvents: "none" }} viewBox="0 -100 70 200" preserveAspectRatio="xMidYMid meet">
    {ticks.map((tk) => (<g key={tk.value} transform={`translate(0 ${-tk.y * 100})`}>
      <line x1={side === "left" ? 0 : 70} x2={side === "left" ? 8 : 62} y1="0" y2="0" stroke="#9fe3c4" strokeWidth="0.5" />
      <text x={side === "left" ? 12 : 58} y="3" fill="#cfe9dd" fontSize="9" textAnchor={anchor} fontFamily="monospace">{tk.value}</text>
    </g>))}
    <text x={side === "left" ? 2 : 68} y="-92" fill="#8b9bb0" fontSize="8" textAnchor={anchor} fontFamily="monospace">{unit}</text>
    <rect x="0" y="-7" width="70" height="14" fill="none" stroke="#3ddc97" strokeWidth="0.6" />
    <text x="35" y="3" fill="#3ddc97" fontSize="10" textAnchor="middle" fontFamily="monospace">{value.toFixed(1)}</text>
  </svg>);
}
