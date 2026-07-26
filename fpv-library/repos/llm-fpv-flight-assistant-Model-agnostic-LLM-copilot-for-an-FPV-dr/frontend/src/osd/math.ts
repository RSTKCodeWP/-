export function headingLabel(deg: number): string {
  const d = ((deg % 360) + 360) % 360;
  const names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return names[Math.round(d / 45) % 8];
}
export function compassTicks(heading: number, windowDeg: number, step: number) {
  const half = windowDeg / 2;
  const ticks: { deg: number; x: number; label: string }[] = [];
  const start = Math.ceil((heading - half) / step) * step;
  for (let d = start; d <= heading + half; d += step) {
    const norm = ((d % 360) + 360) % 360;
    ticks.push({ deg: norm, x: (d - heading) / half, // -1..1
      label: norm % 90 === 0 ? headingLabel(norm) : String(norm) });
  }
  return ticks;
}
export function ladderTicks(value: number, step: number, span: number) {
  const half = span / 2;
  const ticks: { value: number; y: number }[] = [];
  const start = Math.ceil((value - half) / step) * step;
  for (let v = start; v <= value + half; v += step) {
    ticks.push({ value: v, y: (value - v) / half }); // up is positive
  }
  return ticks;
}
