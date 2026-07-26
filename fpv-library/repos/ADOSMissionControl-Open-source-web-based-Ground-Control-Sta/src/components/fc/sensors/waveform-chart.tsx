"use client";

export type SourceTab = "gyro" | "accel" | "mag" | "vibration" | "ekf";
export type TimeWindow = 5 | 15 | 30 | 60;

export interface ImuSample {
  timestamp: number;
  xgyro: number;
  ygyro: number;
  zgyro: number;
  xacc: number;
  yacc: number;
  zacc: number;
  xmag: number;
  ymag: number;
  zmag: number;
}

export const TIME_WINDOWS: TimeWindow[] = [5, 15, 30, 60];
export const TIME_WINDOW_OPTIONS = TIME_WINDOWS.map((w) => ({ value: String(w), label: `${w}s` }));
export const MAX_SAMPLES = 1200;

export const SOURCE_TABS: { key: SourceTab; label: string }[] = [
  { key: "gyro", label: "Gyro" },
  { key: "accel", label: "Accel" },
  { key: "mag", label: "Mag" },
  { key: "vibration", label: "Vibration" },
  { key: "ekf", label: "EKF" },
];

export const AXIS_COLORS = {
  x: "#3A82FF",
  y: "#22c55e",
  z: "#f59e0b",
};

export function WaveformChart({
  data,
  label,
  unit,
  color,
  height = 60,
}: {
  data: number[];
  label: string;
  unit: string;
  color: string;
  height?: number;
}) {
  if (data.length < 2) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-mono text-text-tertiary w-4">{label}</span>
        <div className="flex-1 bg-bg-tertiary/30 rounded flex items-center justify-center" style={{ height }}>
          <span className="text-[9px] text-text-tertiary">Waiting...</span>
        </div>
        <span className="text-[9px] font-mono text-text-tertiary w-16 text-right">{"\u2014"} {unit}</span>
      </div>
    );
  }

  const width = 400;
  const pad = 2;
  const minV = Math.min(...data);
  const maxV = Math.max(...data);
  const range = maxV - minV || 1;

  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - pad - ((v - minV) / range) * (height - pad * 2);
      return `${x},${y}`;
    })
    .join(" ");

  const latest = data[data.length - 1];

  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] font-mono text-text-tertiary w-4">{label}</span>
      <svg viewBox={`0 0 ${width} ${height}`} className="flex-1 bg-bg-tertiary/30 rounded" style={{ height }} preserveAspectRatio="none">
        {minV <= 0 && maxV >= 0 && (
          <line x1="0" y1={height - pad - ((0 - minV) / range) * (height - pad * 2)} x2={width} y2={height - pad - ((0 - minV) / range) * (height - pad * 2)} stroke="var(--border-default)" strokeWidth="0.5" strokeDasharray="4,4" />
        )}
        <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
        <text x={2} y={10} fill="var(--text-tertiary)" fontSize="8" fontFamily="monospace">{maxV.toFixed(1)}</text>
        <text x={2} y={height - 2} fill="var(--text-tertiary)" fontSize="8" fontFamily="monospace">{minV.toFixed(1)}</text>
      </svg>
      <span className="text-[9px] font-mono text-text-tertiary w-16 text-right tabular-nums">{latest.toFixed(1)} {unit}</span>
    </div>
  );
}
