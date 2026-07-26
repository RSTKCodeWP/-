/**
 * LargeVehicleMagCalDialog
 *
 * Single-shot compass calibration for aircraft too large to rotate through
 * all axes for a normal mag cal. The user supplies the vehicle's current
 * true heading (degrees) and AP solves for the offsets using the GPS-derived
 * earth-field vector. Sends MAV_CMD_FIXED_MAG_CAL_YAW (42006) on the FC.
 *
 * Requires GPS 3D lock. A reboot is recommended after a successful run.
 */

import { useEffect, useRef, useState } from 'react';
import { Compass, AlertTriangle, CheckCircle2, Loader2, Satellite } from 'lucide-react';
import { useTelemetryStore } from '../../stores/telemetry-store';

interface LargeVehicleMagCalDialogProps {
  onClose: () => void;
}

type RunState =
  | { kind: 'idle' }
  | { kind: 'running' }
  | { kind: 'success' }
  | { kind: 'error'; message: string };

export function LargeVehicleMagCalDialog({ onClose }: LargeVehicleMagCalDialogProps) {
  const liveHeading = useTelemetryStore((s) => s.vfrHud?.heading ?? 0);
  const gps = useTelemetryStore((s) => s.gps);
  const hasGpsFix = (gps?.fixType ?? 0) >= 3;

  const [headingStr, setHeadingStr] = useState<string>(() =>
    Number.isFinite(liveHeading) ? Math.round(liveHeading).toString() : ''
  );
  const [run, setRun] = useState<RunState>({ kind: 'idle' });
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const headingNum = Number(headingStr);
  const headingValid =
    headingStr.trim() !== '' && Number.isFinite(headingNum) && headingNum >= 0 && headingNum < 360;

  const useLiveHeading = () => {
    setHeadingStr(Math.round(liveHeading).toString());
  };

  const submit = async () => {
    if (!headingValid || run.kind === 'running') return;
    setRun({ kind: 'running' });
    try {
      const result = await window.electronAPI?.calibrationLargeVehicleMagCal(headingNum);
      if (result?.success) {
        setRun({ kind: 'success' });
      } else {
        setRun({ kind: 'error', message: result?.error || 'Command failed' });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setRun({ kind: 'error', message });
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && headingValid && run.kind !== 'running') {
      submit();
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-[60]"
      onClick={onClose}
      onKeyDown={onKeyDown}
    >
      <div
        className="bg-surface-raised rounded-xl border border-subtle w-full max-w-md mx-4 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start gap-3 px-5 pt-5 pb-3">
          <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center shrink-0">
            <Compass className="w-5 h-5 text-amber-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-content">Large Vehicle MagCal</h3>
            <p className="text-xs text-content-secondary mt-1 leading-relaxed">
              Single-shot compass calibration for aircraft that cannot be rotated.
              Point the vehicle in a known true direction and enter the heading below.
            </p>
          </div>
        </div>

        {/* Body */}
        <div className="px-5 pb-4 space-y-3">
          {/* GPS warning */}
          {!hasGpsFix && (
            <div className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-200">
                <span className="font-medium">No GPS 3D lock.</span> A 3D fix is required so the
                FC can derive the local earth-field vector. Calibration will fail without it.
              </div>
            </div>
          )}
          {hasGpsFix && (
            <div className="flex items-center gap-2 p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
              <Satellite className="w-4 h-4 text-emerald-400 shrink-0" />
              <div className="text-xs text-emerald-200">
                GPS 3D fix ({gps?.satellites ?? 0} sats)
              </div>
            </div>
          )}

          {/* Heading input */}
          <div>
            <label className="block text-xs font-medium text-content-secondary mb-1.5">
              Current True Heading (degrees)
            </label>
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="number"
                inputMode="decimal"
                min={0}
                max={359.9}
                step={0.1}
                value={headingStr}
                onChange={(e) => setHeadingStr(e.target.value)}
                onKeyDown={onKeyDown}
                disabled={run.kind === 'running' || run.kind === 'success'}
                placeholder="0 - 359"
                className="flex-1 px-3 py-2 text-sm rounded-lg bg-surface border border-subtle focus:border-amber-400/60 focus:outline-none focus:ring-1 focus:ring-amber-400/40 text-content disabled:opacity-50"
              />
              <button
                type="button"
                onClick={useLiveHeading}
                disabled={run.kind === 'running' || run.kind === 'success'}
                className="px-3 py-2 text-xs rounded-lg bg-surface border border-subtle hover:border-amber-400/60 hover:text-amber-300 text-content-secondary transition-colors disabled:opacity-50"
                title={`Use live heading (${Math.round(liveHeading)}°)`}
              >
                Use Live ({Math.round(liveHeading)}°)
              </button>
            </div>
            <p className="text-[11px] text-content-tertiary mt-1.5 leading-relaxed">
              Heading is true (not magnetic). Use a known landmark, runway alignment,
              or a separate compass. Accuracy directly affects calibration quality.
            </p>
          </div>

          {/* Run state feedback */}
          {run.kind === 'running' && (
            <div className="flex items-center gap-2 p-2.5 rounded-lg bg-blue-500/10 border border-blue-500/30">
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin shrink-0" />
              <div className="text-xs text-blue-200">Sending calibration command...</div>
            </div>
          )}
          {run.kind === 'success' && (
            <div className="flex items-start gap-2 p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div className="text-xs text-emerald-200">
                <span className="font-medium">Calibration complete.</span> Compass offsets
                have been written. A reboot is recommended for the new offsets to take effect.
              </div>
            </div>
          )}
          {run.kind === 'error' && (
            <div className="flex items-start gap-2 p-2.5 rounded-lg bg-red-500/10 border border-red-500/30">
              <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <div className="text-xs text-red-200">{run.message}</div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-subtle">
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg text-xs text-content-secondary hover:text-content hover:bg-surface transition-colors"
          >
            {run.kind === 'success' ? 'Close' : 'Cancel'}
          </button>
          {run.kind !== 'success' && (
            <button
              onClick={submit}
              disabled={!headingValid || run.kind === 'running'}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-amber-600 hover:bg-amber-500 disabled:bg-amber-600/40 disabled:cursor-not-allowed transition-colors"
            >
              {run.kind === 'running' ? 'Running...' : 'Run Calibration'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default LargeVehicleMagCalDialog;
