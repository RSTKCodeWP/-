"use client";

import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
  ReferenceDot,
} from "recharts";
import type { FFTAxisResult } from "@/lib/analysis/types";

interface PidFFTChartProps {
  data: FFTAxisResult;
  color?: string;
}

export function PidFFTChart({ data, color = "#3A82FF" }: PidFFTChartProps) {
  const chartData = useMemo(
    () =>
      data.spectrum
        .filter((b) => b.frequency <= 500)
        .map((b) => ({
          frequency: Math.round(b.frequency * 10) / 10,
          magnitude: Math.round(b.magnitude * 100) / 100,
        })),
    [data.spectrum],
  );

  const peaks = useMemo(
    () =>
      data.peaks.slice(0, 5).map((p) => ({
        frequency: Math.round(p.frequency * 10) / 10,
        magnitudeDb: Math.round(p.magnitudeDb * 10) / 10,
        zone: p.zone,
      })),
    [data.peaks],
  );

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-[200px] text-[10px] text-text-tertiary">
        No FFT data
      </div>
    );
  }

  return (
    <div className="h-[200px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis
            dataKey="frequency"
            type="number"
            domain={[0, 500]}
            tick={{ fill: "#6b7280", fontSize: 10 }}
            label={{ value: "Hz", position: "insideBottomRight", offset: -4, fill: "#6b7280", fontSize: 10 }}
          />
          <YAxis
            tick={{ fill: "#6b7280", fontSize: 10 }}
            label={{ value: "dB", angle: -90, position: "insideLeft", fill: "#6b7280", fontSize: 10 }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#111827",
              border: "1px solid #1f2937",
              borderRadius: 0,
              fontSize: 11,
            }}
            labelStyle={{ color: "#9ca3af" }}
            formatter={(value: number) => [`${value.toFixed(2)} dB`, "Magnitude"]}
            labelFormatter={(label: number) => `${label} Hz`}
          />
          <ReferenceArea
            x1={20}
            x2={100}
            fill="#f59e0b"
            fillOpacity={0.1}
            label={{ value: "Propwash", fill: "#f59e0b", fontSize: 9, position: "insideTopLeft" }}
          />
          <ReferenceArea
            x1={200}
            x2={400}
            fill="#ef4444"
            fillOpacity={0.1}
            label={{ value: "Motor Noise", fill: "#ef4444", fontSize: 9, position: "insideTopLeft" }}
          />
          <Line
            type="monotone"
            dataKey="magnitude"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
          {peaks.map((peak, i) => (
            <ReferenceDot
              key={i}
              x={peak.frequency}
              y={peak.magnitudeDb}
              r={3}
              fill={peak.zone === "propwash" ? "#f59e0b" : peak.zone === "motor" ? "#ef4444" : color}
              stroke="none"
              label={{
                value: `${peak.frequency}Hz`,
                position: "top",
                fill: "#9ca3af",
                fontSize: 9,
              }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
