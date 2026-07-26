export function Crosshair() {
  return (<svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }} viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
    <g stroke="#3ddc97" strokeWidth="0.4" fill="none" opacity="0.9">
      <line x1="46" y1="50" x2="49" y2="50" /><line x1="51" y1="50" x2="54" y2="50" />
      <line x1="50" y1="46" x2="50" y2="49" /><line x1="50" y1="51" x2="50" y2="54" />
    </g></svg>);
}
