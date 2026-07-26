import { useCallback, useEffect, useState, useMemo } from 'react';
import { AlertTriangle, CheckCircle, XCircle, Info, Cpu } from 'lucide-react';
import { useParameterStore } from '../../stores/parameter-store.js';
import { useConnectionStore } from '../../stores/connection-store.js';
import { useNavigationStore } from '../../stores/navigation-store.js';
import { classifySitlUnsafeParam } from '../../../shared/sitl-unsafe-params.js';
import { formatParamValue } from '../../../shared/parameter-types.js';

/**
 * Global parameter compare/apply modal. Mounted once at App root so it's
 * visible regardless of current view — critical because several flows drive
 * it (manual file load in Parameters view, Vehicle Profile apply in Settings,
 * assistant MCP `propose_parameters`, etc.) and the user would otherwise need
 * to manually navigate to Parameters view just to see the dialog.
 *
 * ParameterTable suppresses its own copy when this root instance exists,
 * except for the reboot-cycle flow which remains Parameters-view-only
 * (power feature, not needed for SITL).
 */
export function ParameterCompareModalRoot() {
  const currentView = useNavigationStore(s => s.currentView);
  // ParameterTable renders its own modal when on Parameters view so we don't
  // duplicate. This root instance covers every other view.
  if (currentView === 'parameters') return null;
  return <CompareModal />;
}

function CompareModal() {
  const showCompareModal = useParameterStore(s => s.showCompareModal);
  const fileParamDiffs = useParameterStore(s => s.fileParamDiffs);
  const fileApplyResult = useParameterStore(s => s.fileApplyResult);
  const fileSkippedCount = useParameterStore(s => s.fileSkippedCount);
  const fileTotalCount = useParameterStore(s => s.fileTotalCount);
  const fileVehicleType = useParameterStore(s => s.fileVehicleType);
  const isApplyingFileParams = useParameterStore(s => s.isApplyingFileParams);
  const applyProgress = useParameterStore(s => s.applyProgress);
  const closeCompareModal = useParameterStore(s => s.closeCompareModal);
  const toggleDiffSelection = useParameterStore(s => s.toggleDiffSelection);
  const selectAllDiffs = useParameterStore(s => s.selectAllDiffs);
  const deselectAllDiffs = useParameterStore(s => s.deselectAllDiffs);
  const applySelectedFileParams = useParameterStore(s => s.applySelectedFileParams);
  const clearFileApplyResult = useParameterStore(s => s.clearFileApplyResult);
  const connectionState = useConnectionStore(s => s.connectionState);

  const handleApply = useCallback(async () => {
    await applySelectedFileParams();
  }, [applySelectedFileParams]);

  const handleSummaryClose = useCallback(() => {
    clearFileApplyResult();
    closeCompareModal();
  }, [clearFileApplyResult, closeCompareModal]);

  const jumpToParameters = useCallback(() => {
    useNavigationStore.getState().setView('parameters');
  }, []);

  if (!showCompareModal) return null;

  return (
    <div className="fixed inset-0 bg-surface-overlay flex items-center justify-center z-[120]">
      <div className="bg-surface border border-subtle rounded-xl shadow-2xl max-w-2xl w-full mx-4 max-h-[640px] h-[640px] flex flex-col overflow-hidden">
        {fileApplyResult ? (
          <SummaryView
            result={fileApplyResult}
            onClose={handleSummaryClose}
            onGoToParameters={jumpToParameters}
          />
        ) : (
          <CompareView
            diffs={fileParamDiffs}
            skippedCount={fileSkippedCount}
            totalCount={fileTotalCount}
            fileVehicleType={fileVehicleType}
            currentVehicleType={connectionState.vehicleType || connectionState.fcVariant}
            isSitl={!!connectionState.isSitl}
            isApplying={isApplyingFileParams}
            progress={applyProgress}
            onToggle={toggleDiffSelection}
            onSelectAll={selectAllDiffs}
            onDeselectAll={deselectAllDiffs}
            onApply={handleApply}
            onCancel={closeCompareModal}
          />
        )}
      </div>
    </div>
  );
}

interface CompareViewProps {
  diffs: ReturnType<typeof useParameterStore.getState>['fileParamDiffs'];
  skippedCount: number;
  totalCount: number;
  fileVehicleType: string | null;
  currentVehicleType: string | undefined;
  isSitl: boolean;
  isApplying: boolean;
  progress: { applied: number; total: number } | null;
  onToggle: (paramId: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  onApply: () => void;
  onCancel: () => void;
}

function CompareView({
  diffs, skippedCount, totalCount, fileVehicleType, currentVehicleType, isSitl,
  isApplying, progress, onToggle, onSelectAll, onDeselectAll, onApply, onCancel,
}: CompareViewProps) {
  // SITL-safe mode: filter out hardware-identity / hardware-bus params that
  // would crash a simulated FC (HAL panic on unmodeled peripheral registers).
  // Defaults ON when the active connection is a SITL target. User can disable
  // it to override and show / select all params anyway.
  const [safeMode, setSafeMode] = useState(isSitl);
  // Sync defaults when the modal is reopened against a different connection.
  useEffect(() => { setSafeMode(isSitl); }, [isSitl]);

  // Classify each diff once. paramId+fileValue uniquely determine the verdict.
  const unsafeMap = useMemo(() => {
    const m = new Map<string, string>();
    for (const d of diffs) {
      const verdict = classifySitlUnsafeParam(d.paramId, d.fileValue);
      if (verdict) m.set(d.paramId, verdict.reason);
    }
    return m;
  }, [diffs]);

  // When SITL-safe mode is on, deselect any unsafe rows that may already be
  // selected (e.g., from a prior pass with safe mode off, or from the store's
  // default-everything-selected state). Runs whenever the diff set changes
  // or safe mode flips on.
  useEffect(() => {
    if (!safeMode) return;
    for (const d of diffs) {
      if (d.selected && unsafeMap.has(d.paramId)) {
        onToggle(d.paramId);
      }
    }
  }, [safeMode, diffs, unsafeMap, onToggle]);

  const visibleDiffs = safeMode ? diffs.filter(d => !unsafeMap.has(d.paramId)) : diffs;
  const hiddenUnsafeCount = diffs.length - visibleDiffs.length;
  const selectedCount = visibleDiffs.filter(d => d.selected).length;
  return (
    <>
      <div className="px-6 py-4 border-b border-subtle">
        <h3 className="text-lg font-semibold text-content">Review parameter changes</h3>
        <p className="text-sm text-content-secondary mt-1">
          {diffs.length === 0
            ? 'No differences found — all parameters already match the vehicle.'
            : `${diffs.length} parameter${diffs.length !== 1 ? 's' : ''} will change. Pick which to apply.`}
        </p>
        {fileVehicleType && currentVehicleType && fileVehicleType !== currentVehicleType && (
          <div className="mt-2 flex items-center gap-2 px-3 py-2 bg-amber-500/10 border border-amber-500/30 rounded-lg">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span className="text-xs text-amber-300">
              Source vehicle <span className="font-semibold">{fileVehicleType}</span> differs from connected vehicle <span className="font-semibold">{currentVehicleType}</span>
            </span>
          </div>
        )}
        {skippedCount > 0 && (
          <p className="text-xs text-content-secondary mt-2">
            {totalCount} total: {totalCount - skippedCount} matched the vehicle, {skippedCount} skipped (not on this firmware)
          </p>
        )}
        {isSitl && unsafeMap.size > 0 && (
          <div className="mt-3 flex items-start gap-2 px-3 py-2 bg-blue-500/10 border border-blue-500/30 rounded-lg">
            <Cpu className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
            <div className="flex-1 text-xs">
              <div className="text-blue-300">
                {safeMode
                  ? `SITL-safe mode hides ${unsafeMap.size} hardware-identity param${unsafeMap.size !== 1 ? 's' : ''} that can crash the simulator.`
                  : `${unsafeMap.size} param${unsafeMap.size !== 1 ? 's' : ''} below are flagged as hardware-only and may crash SITL on reboot.`}
              </div>
              <button
                onClick={() => setSafeMode(v => !v)}
                className="mt-1 text-blue-400 hover:text-blue-300 underline transition-colors"
              >
                {safeMode ? 'Show all (override)' : 'Re-enable SITL-safe mode'}
              </button>
            </div>
          </div>
        )}
      </div>

      {diffs.length > 0 && (
        <>
          <div className="px-6 py-2 border-b border-subtle flex items-center gap-3">
            <button onClick={onSelectAll} className="text-xs text-blue-400 hover:text-blue-300 transition-colors">Select all</button>
            <span className="text-content-tertiary">|</span>
            <button onClick={onDeselectAll} className="text-xs text-content-secondary hover:text-content transition-colors">Deselect all</button>
            <span className="ml-auto text-xs text-content-secondary">
              {selectedCount} of {visibleDiffs.length} selected{hiddenUnsafeCount > 0 ? ` (${hiddenUnsafeCount} hw-only hidden)` : ''}
            </span>
          </div>

          <div className="flex-1 min-h-0 overflow-auto px-6 py-2">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-content-secondary uppercase">
                  <th className="pb-2 w-8"></th>
                  <th className="pb-2">Parameter</th>
                  <th className="pb-2 text-right">Current</th>
                  <th className="pb-2 text-center w-8"></th>
                  <th className="pb-2">Target</th>
                  <th className="pb-2 pl-3">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-subtle">
                {visibleDiffs.map(diff => {
                  const unsafeReason = unsafeMap.get(diff.paramId);
                  return (
                    <tr
                      key={diff.paramId}
                      onClick={() => onToggle(diff.paramId)}
                      className={`cursor-pointer transition-colors ${diff.selected ? 'hover:bg-surface-overlay-subtle' : 'opacity-50 hover:opacity-75'}`}
                    >
                      <td className="py-2 pr-2">
                        <div className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                          diff.selected ? 'bg-blue-500/30 border-blue-500/50' : 'border-subtle bg-surface'
                        }`}>
                          {diff.selected && (
                            <svg className="w-3 h-3 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                        </div>
                      </td>
                      <td className="py-2 font-mono text-content">
                        {diff.paramId}
                        {unsafeReason && (
                          <span
                            className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-[9px] uppercase tracking-wide font-medium bg-red-500/15 text-red-400 border border-red-500/30"
                            title={`SITL-unsafe: ${unsafeReason}. Applying may crash the simulator.`}
                          >
                            hw-only
                          </span>
                        )}
                      </td>
                      <td className="py-2 text-right font-mono text-content-secondary">{formatParamValue(diff.currentValue)}</td>
                      <td className="py-2 text-center text-content-tertiary">
                        <svg className="w-3 h-3 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                        </svg>
                      </td>
                      <td className="py-2 font-mono text-amber-400">{formatParamValue(diff.fileValue)}</td>
                      <td className="py-2 pl-3 text-xs text-content-secondary truncate max-w-[200px]" title={unsafeReason ?? diff.note}>
                        {unsafeReason ?? diff.note ?? ''}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {isApplying && progress && (
        <div className="px-6 py-2 border-t border-subtle">
          <div className="flex items-center justify-between text-xs text-content-secondary mb-1">
            <span>Writing parameters…</span>
            <span>{progress.applied} / {progress.total}</span>
          </div>
          <div className="h-1.5 bg-surface-inset rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all duration-150"
              style={{ width: `${(progress.applied / progress.total) * 100}%` }}
            />
          </div>
        </div>
      )}

      <div className="px-6 py-4 border-t border-subtle flex justify-end gap-3">
        <button
          onClick={onCancel}
          disabled={isApplying}
          className="px-4 py-2 text-sm text-content-secondary hover:text-content disabled:text-content-tertiary transition-colors"
        >
          {diffs.length === 0 ? 'Close' : 'Cancel'}
        </button>
        {diffs.length > 0 && (
          <button
            onClick={onApply}
            disabled={isApplying || selectedCount === 0}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-surface-raised text-white disabled:text-content-tertiary rounded-lg text-sm font-medium transition-colors"
          >
            {isApplying ? 'Writing…' : `Apply ${selectedCount} param${selectedCount !== 1 ? 's' : ''}`}
          </button>
        )}
      </div>
    </>
  );
}

interface SummaryViewProps {
  result: NonNullable<ReturnType<typeof useParameterStore.getState>['fileApplyResult']>;
  onClose: () => void;
  onGoToParameters: () => void;
}

function SummaryView({ result, onClose, onGoToParameters }: SummaryViewProps) {
  return (
    <>
      <div className="px-6 py-4 border-b border-subtle">
        <h3 className="text-lg font-semibold text-content">Apply results</h3>
      </div>
      <div className="flex-1 min-h-0 overflow-auto px-6 py-5 space-y-4">
        <div className="flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0" />
          <span className="text-sm text-emerald-300">
            {result.applied} parameter{result.applied !== 1 ? 's' : ''} applied
          </span>
        </div>
        {result.failed > 0 && (
          <div className="flex items-center gap-3">
            <XCircle className="w-5 h-5 text-red-400 shrink-0" />
            <span className="text-sm text-red-300">
              {result.failed} parameter{result.failed !== 1 ? 's' : ''} failed
            </span>
          </div>
        )}
        {result.rebootRequired.length > 0 && (
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <span className="text-sm text-amber-300">
                {result.rebootRequired.length} require reboot to take effect:
              </span>
              <p className="font-mono text-xs text-amber-400/70 mt-1 break-words">
                {result.rebootRequired.join(', ')}
              </p>
              <button
                onClick={onGoToParameters}
                className="mt-2 text-xs text-amber-300 underline hover:text-amber-200"
              >
                Go to Parameters tab to flash + reboot
              </button>
            </div>
          </div>
        )}
        {result.skippedParams.length > 0 && (
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
            <div>
              <span className="text-sm text-blue-300">
                {result.skippedParams.length} not found on this firmware:
              </span>
              <p className="font-mono text-xs text-blue-400/70 mt-1 break-words">
                {result.skippedParams.map(p => p.id).join(', ')}
              </p>
              <p className="text-xs text-content-secondary mt-1">
                These may become available after reboot
              </p>
            </div>
          </div>
        )}
      </div>
      <div className="px-6 py-4 border-t border-subtle flex justify-end gap-3">
        <button
          onClick={onClose}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
        >
          Done
        </button>
      </div>
    </>
  );
}

