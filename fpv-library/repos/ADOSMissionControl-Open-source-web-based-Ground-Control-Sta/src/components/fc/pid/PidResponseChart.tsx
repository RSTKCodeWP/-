"use client";

export function PidResponseChart({
  data,
  label,
  color,
  height = 50,
}: {
  data: number[];
  label: string;
  color: string;
  height?: number;
}) {
  const width = 300;
  if (data.length < 2) return null;
  const minV = Math.min(...data);
  const maxV = Math.max(...data);
  const range = maxV - minV || 1;
  const pad = 2;

  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - pad - ((v - minV) / range) * (height - pad * 2);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[9px] font-mono text-text-tertiary w-8">{label}</span>
      <svg viewBox={`0 0 ${width} ${height}`} className="flex-1 h-[50px] bg-bg-tertiary/30 rounded" preserveAspectRatio="none">
        <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
      </svg>
      <span className="text-[9px] font-mono text-text-tertiary w-12 text-right tabular-nums">
        {data[data.length - 1]?.toFixed(1)}&deg;
      </span>
    </div>
  );
}
