import { compassTicks } from "../../osd/math";
export function CompassTape({ heading }: { heading: number }) {
  const ticks = compassTicks(heading, 90, 15);
  return (<svg style={{ position: "absolute", top: 8, left: "50%", transform: "translateX(-50%)", width: "60%", height: 34, pointerEvents: "none" }} viewBox="-100 0 200 34" preserveAspectRatio="xMidYMid meet">
    {ticks.map((tk) => (<g key={tk.deg + "-" + tk.x} transform={`translate(${tk.x * 100} 0)`}>
      <line x1="0" y1="6" x2="0" y2="14" stroke="#9fe3c4" strokeWidth="0.6" />
      <text x="0" y="26" fill="#cfe9dd" fontSize="9" textAnchor="middle" fontFamily="monospace">{tk.label}</text>
    </g>))}
    <polygon points="0,2 -3,-4 3,-4" fill="#3ddc97" /></svg>);
}
