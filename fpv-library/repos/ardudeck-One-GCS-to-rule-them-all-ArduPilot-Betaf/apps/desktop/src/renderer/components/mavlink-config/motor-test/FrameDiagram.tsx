/**
 * FrameDiagram — SVG visualization of the physical motor layout.
 *
 * Pure visual component. Accepts a frame layout, an optional active-motor
 * highlight, and an optional RPM map. Emits onMotorClick when the user
 * clicks a motor circle.
 */

import React from 'react';
import type { FrameLayout } from '../../../../shared/motor-test-types';
import { layoutToSvgPositions, testOrderToLabel } from './motor-layout-utils';

interface FrameDiagramProps {
  layout: FrameLayout;
  /** Motor number (1-based) currently being tested, or null */
  activeMotor: number | null;
  /** Map of motor number (1-based) → RPM */
  rpmByMotor?: Map<number, number>;
  /** Called when user clicks a motor circle */
  onMotorClick?: (motorNumber: number) => void;
  /** Canvas size in px (square) */
  size?: number;
}

export const FrameDiagram: React.FC<FrameDiagramProps> = ({
  layout,
  activeMotor,
  rpmByMotor,
  onMotorClick,
  size = 340,
}) => {
  const positions = layoutToSvgPositions(layout, size);
  const center = size / 2;
  const motorRadius = 26;

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="text-center">
        <div className="text-xs uppercase tracking-wider text-content-secondary">Frame</div>
        <div className="text-sm text-content">
          {layout.ClassName} <span className="text-content-secondary">·</span> {layout.TypeName}
        </div>
      </div>

      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="rounded-xl bg-surface border border-subtle"
      >
        {/* Center reference circle (vehicle body) */}
        <circle
          cx={center}
          cy={center}
          r={size / 2 - 60}
          fill="none"
          stroke="var(--border-default)"
          strokeWidth={1}
          strokeDasharray="3 4"
        />

        {/* Forward indicator (up arrow at top) */}
        <g>
          <line
            x1={center}
            y1={center}
            x2={center}
            y2={34}
            stroke="var(--border-default)"
            strokeWidth={1.5}
          />
          <polygon
            points={`${center - 6},40 ${center + 6},40 ${center},28`}
            fill="var(--text-tertiary)"
          />
          <text
            x={center}
            y={22}
            textAnchor="middle"
            fill="var(--text-secondary)"
            fontSize={11}
            fontFamily="monospace"
          >
            FWD
          </text>
        </g>

        {/* Motor arms — lines from center to each motor */}
        {positions.map((pos) => (
          <line
            key={`arm-${pos.number}`}
            x1={center}
            y1={center}
            x2={pos.cx}
            y2={pos.cy}
            stroke="var(--border-default)"
            strokeWidth={2}
          />
        ))}

        {/* Motor circles */}
        {positions.map((pos) => {
          const isActive = activeMotor === pos.number;
          const rpm = rpmByMotor?.get(pos.number);
          const isCw = pos.rotation === 'CW';
          const color = isCw ? 'rgb(59, 130, 246)' : 'rgb(16, 185, 129)'; // blue = CW, green = CCW

          return (
            <g
              key={`motor-${pos.number}`}
              className={onMotorClick ? 'cursor-pointer' : ''}
              onClick={() => onMotorClick?.(pos.number)}
            >
              {/* Active motor glow */}
              {isActive && (
                <circle
                  cx={pos.cx}
                  cy={pos.cy}
                  r={motorRadius + 8}
                  fill="none"
                  stroke="rgb(250, 204, 21)"
                  strokeWidth={3}
                  opacity={0.7}
                >
                  <animate
                    attributeName="r"
                    from={motorRadius + 4}
                    to={motorRadius + 12}
                    dur="1.2s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    from={0.7}
                    to={0.1}
                    dur="1.2s"
                    repeatCount="indefinite"
                  />
                </circle>
              )}

              {/* Motor body */}
              <circle
                cx={pos.cx}
                cy={pos.cy}
                r={motorRadius}
                fill="var(--bg-base)"
                stroke={isActive ? 'rgb(250, 204, 21)' : color}
                strokeWidth={isActive ? 3 : 2}
              />

              {/* Rotation arrow — small arc with arrowhead */}
              <g opacity={0.7}>
                <path
                  d={
                    isCw
                      ? `M ${pos.cx - 14} ${pos.cy - 4} A 14 14 0 1 1 ${pos.cx + 14} ${pos.cy - 4}`
                      : `M ${pos.cx + 14} ${pos.cy - 4} A 14 14 0 1 0 ${pos.cx - 14} ${pos.cy - 4}`
                  }
                  fill="none"
                  stroke={color}
                  strokeWidth={1.5}
                />
              </g>

              {/* Motor number (large) */}
              <text
                x={pos.cx}
                y={pos.cy + 2}
                textAnchor="middle"
                fill="var(--text-primary)"
                fontSize={16}
                fontWeight="bold"
                fontFamily="monospace"
                pointerEvents="none"
              >
                {pos.number}
              </text>

              {/* Test order label (A/B/C below motor) */}
              <text
                x={pos.cx}
                y={pos.cy + motorRadius + 14}
                textAnchor="middle"
                fill="var(--text-secondary)"
                fontSize={11}
                fontFamily="monospace"
                pointerEvents="none"
              >
                {testOrderToLabel(pos.testOrder)}
              </text>

              {/* RPM (if available) */}
              {rpm !== undefined && rpm > 0 && (
                <text
                  x={pos.cx}
                  y={pos.cy + motorRadius + 27}
                  textAnchor="middle"
                  fill="rgb(250, 204, 21)"
                  fontSize={10}
                  fontFamily="monospace"
                  pointerEvents="none"
                >
                  {rpm} rpm
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="flex items-center gap-4 text-[11px] text-content-secondary">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full border-2 border-blue-500" />
          CW
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full border-2 border-emerald-500" />
          CCW
        </div>
        <div className="text-content-tertiary">Click a motor to test</div>
      </div>
    </div>
  );
};
