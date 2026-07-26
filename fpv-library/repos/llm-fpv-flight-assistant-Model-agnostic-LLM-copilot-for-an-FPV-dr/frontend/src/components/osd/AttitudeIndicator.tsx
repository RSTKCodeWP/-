export function AttitudeIndicator({ roll, pitch }: { roll: number; pitch: number }) {
  const t = `translate(0 ${pitch * 0.8}) rotate(${-roll} 50 50)`;
  return (<svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none", opacity: 0.7 }} viewBox="0 0 100 100" preserveAspectRatio="none">
    <g transform={t} stroke="#9fe3c4" strokeWidth="0.3">
      <line x1="20" y1="50" x2="80" y2="50" />
      {[-20, -10, 10, 20].map((p) => (<line key={p} x1="42" x2="58" y1={50 - p * 0.8} y2={50 - p * 0.8} />))}
    </g></svg>);
}
