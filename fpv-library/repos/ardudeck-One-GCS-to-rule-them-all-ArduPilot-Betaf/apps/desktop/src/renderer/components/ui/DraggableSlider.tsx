/**
 * Draggable Slider Component
 *
 * A reusable slider with proper drag support that updates values in real-time
 * while dragging, not just on release.
 *
 * Features:
 * - Pointer events for touch/mouse support
 * - Real-time value updates during drag
 * - Visible thumb handle
 * - Optional +/- buttons
 * - Number input for precise values
 */

import { useRef, useCallback, useMemo } from 'react';

export interface DraggableSliderProps {
  /** Current value */
  value: number;
  /** Called on value change (during drag and on click) */
  onChange: (value: number) => void;
  /** Minimum value */
  min?: number;
  /** Maximum value */
  max?: number;
  /** Step increment for +/- buttons */
  step?: number;
  /** Slider track color */
  color?: string;
  /** Label text */
  label?: string;
  /** Hint text below label */
  hint?: string;
  /** Show +/- buttons and number input */
  showControls?: boolean;
  /** Slider height in pixels */
  height?: number;
  /** Show thumb handle */
  showThumb?: boolean;
  /** Disabled state - grays out and prevents interaction */
  disabled?: boolean;
  /** Unit label (informational, not rendered by slider) */
  unit?: string;
  /** Custom value formatter */
  formatValue?: (value: number) => string;
}

export function DraggableSlider({
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  color = '#3B82F6',
  label,
  hint,
  showControls = true,
  height = 12,
  showThumb = true,
  disabled = false,
}: DraggableSliderProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  const percentage = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));

  // Muted color for disabled state
  const effectiveColor = disabled ? '#52525b' : color;

  // Round to step precision so 48 + 0.01 doesn't yield 48.00999983...
  // The number of decimals comes from the step itself: step=0.01 → 2 decimals.
  const stepDecimals = useMemo(() => {
    const s = String(step);
    const dot = s.indexOf('.');
    return dot >= 0 ? s.length - dot - 1 : 0;
  }, [step]);

  const roundToStep = useCallback(
    (v: number) => {
      const factor = Math.pow(10, stepDecimals);
      return Math.round(v * factor) / factor;
    },
    [stepDecimals]
  );

  const calculateValue = useCallback(
    (clientX: number): number => {
      if (!trackRef.current) return value;
      const rect = trackRef.current.getBoundingClientRect();
      const x = clientX - rect.left;
      const ratio = Math.max(0, Math.min(1, x / rect.width));
      const raw = Math.round((ratio * (max - min) + min) / step) * step;
      const newValue = roundToStep(raw);
      return Math.max(min, Math.min(max, newValue));
    },
    [min, max, step, value, roundToStep]
  );

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (disabled) return;
      e.preventDefault();
      isDragging.current = true;
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      const newValue = calculateValue(e.clientX);
      if (newValue !== value) {
        onChange(newValue);
      }
    },
    [calculateValue, onChange, value, disabled]
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (disabled || !isDragging.current) return;
      const newValue = calculateValue(e.clientX);
      if (newValue !== value) {
        onChange(newValue);
      }
    },
    [calculateValue, onChange, value, disabled]
  );

  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    isDragging.current = false;
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
  }, []);

  const handleIncrement = useCallback(() => {
    if (disabled) return;
    onChange(Math.min(max, roundToStep(value + step)));
  }, [max, onChange, step, value, disabled, roundToStep]);

  const handleDecrement = useCallback(() => {
    if (disabled) return;
    onChange(Math.max(min, roundToStep(value - step)));
  }, [min, onChange, step, value, disabled, roundToStep]);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (disabled) return;
      // Accept both '.' and ',' as decimal separators (locale-tolerant).
      const raw = e.target.value.replace(',', '.');
      const parsed = parseFloat(raw);
      const newValue = Number.isFinite(parsed) ? parsed : min;
      onChange(Math.max(min, Math.min(max, newValue)));
    },
    [max, min, onChange, disabled]
  );

  return (
    <div className={disabled ? 'opacity-60' : ''}>
      {/* Label and controls row */}
      {(label || showControls) && (
        <div className="flex items-start justify-between mb-2">
          {label && (
            <div className="min-w-0">
              <span className={`text-sm font-medium ${disabled ? 'text-content-secondary' : 'text-content'}`}>{label}</span>
              {hint && <p className="text-xs text-content-secondary mt-0.5">{hint}</p>}
            </div>
          )}
          {showControls && (
            <div className="flex items-center gap-2">
              <button
                onClick={handleDecrement}
                disabled={disabled}
                className={`w-6 h-6 rounded text-sm flex items-center justify-center ${
                  disabled
                    ? 'bg-surface-raised text-content-tertiary cursor-not-allowed'
                    : 'bg-surface-raised hover:bg-surface text-content-secondary'
                }`}
              >
                -
              </button>
              <input
                type="text"
                inputMode="decimal"
                value={roundToStep(value).toFixed(stepDecimals)}
                onChange={handleInputChange}
                disabled={disabled}
                className={`min-w-[5rem] w-auto px-2 py-1 text-center text-sm border rounded tabular-nums ${
                  disabled
                    ? 'bg-surface-input border-subtle text-content-secondary cursor-not-allowed'
                    : 'bg-surface-input border-border text-content'
                }`}
                style={{ width: `${Math.max(5, roundToStep(value).toFixed(stepDecimals).length + 2)}ch` }}
              />
              <button
                onClick={handleIncrement}
                disabled={disabled}
                className={`w-6 h-6 rounded text-sm flex items-center justify-center ${
                  disabled
                    ? 'bg-surface-raised text-content-tertiary cursor-not-allowed'
                    : 'bg-surface-raised hover:bg-surface text-content-secondary'
                }`}
              >
                +
              </button>
            </div>
          )}
        </div>
      )}

      {/* Slider track */}
      <div
        ref={trackRef}
        className={`relative bg-surface-inset rounded-full touch-none select-none ${
          disabled ? 'cursor-not-allowed' : 'cursor-pointer'
        }`}
        style={{ height }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
      >
        {/* Progress fill */}
        <div
          className="absolute left-0 top-0 h-full rounded-full pointer-events-none"
          style={{ width: `${percentage}%`, backgroundColor: effectiveColor }}
        />

        {/* Thumb handle */}
        {showThumb && (
          <div
            className={`absolute top-1/2 -translate-y-1/2 rounded-full shadow-lg border-2 pointer-events-none ${
              disabled ? 'bg-content-secondary' : 'bg-white'
            }`}
            style={{
              width: height + 4,
              height: height + 4,
              left: `calc(${percentage}% - ${(height + 4) / 2}px)`,
              borderColor: effectiveColor,
            }}
          />
        )}
      </div>
    </div>
  );
}

/**
 * Compact slider variant for space-constrained UIs
 * Smaller controls, no hint text
 */
export function CompactSlider({
  value,
  onChange,
  min = 0,
  max = 100,
  step = 10,
  color = '#3B82F6',
  label,
}: Omit<DraggableSliderProps, 'hint' | 'showControls' | 'height' | 'showThumb'>) {
  const trackRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  const percentage = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));

  const calculateValue = useCallback(
    (clientX: number): number => {
      if (!trackRef.current) return value;
      const rect = trackRef.current.getBoundingClientRect();
      const x = clientX - rect.left;
      const ratio = Math.max(0, Math.min(1, x / rect.width));
      const newValue = Math.round((ratio * (max - min) + min) / step) * step;
      return Math.max(min, Math.min(max, newValue));
    },
    [min, max, step, value]
  );

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      isDragging.current = true;
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      const newValue = calculateValue(e.clientX);
      if (newValue !== value) {
        onChange(newValue);
      }
    },
    [calculateValue, onChange, value]
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!isDragging.current) return;
      const newValue = calculateValue(e.clientX);
      if (newValue !== value) {
        onChange(newValue);
      }
    },
    [calculateValue, onChange, value]
  );

  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    isDragging.current = false;
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
  }, []);

  return (
    <div className="space-y-1">
      {label && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-content-secondary">{label}</span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onChange(Math.max(min, value - step))}
              className="w-5 h-5 rounded bg-surface-raised hover:bg-surface text-content-secondary text-xs flex items-center justify-center"
            >
              -
            </button>
            <input
              type="number"
              min={min}
              max={max}
              value={value}
              onChange={(e) => onChange(Math.max(min, Math.min(max, parseInt(e.target.value) || min)))}
              className="min-w-[5rem] w-auto px-2 py-0.5 text-center text-sm bg-surface-input border border-border rounded text-content tabular-nums"
              style={{ width: `${Math.max(5, String(value).length + 2)}ch` }}
            />
            <button
              onClick={() => onChange(Math.min(max, value + step))}
              className="w-5 h-5 rounded bg-surface-raised hover:bg-surface text-content-secondary text-xs flex items-center justify-center"
            >
              +
            </button>
          </div>
        </div>
      )}

      {/* Slider track with thumb */}
      <div
        ref={trackRef}
        className="relative h-2 bg-surface-inset rounded-full cursor-pointer touch-none select-none"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
      >
        {/* Progress fill */}
        <div
          className="absolute left-0 top-0 h-full rounded-full pointer-events-none"
          style={{ width: `${percentage}%`, backgroundColor: color }}
        />

        {/* Thumb handle - slightly larger for visibility */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white shadow-md border-2 pointer-events-none"
          style={{
            left: `calc(${percentage}% - 6px)`,
            borderColor: color,
          }}
        />
      </div>
    </div>
  );
}

export default DraggableSlider;
