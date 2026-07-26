import { useEffect, useMemo, useState } from 'react';
import { useLogStore, type LogListEntry } from '../../stores/log-store';
import { useConnectionStore } from '../../stores/connection-store';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(utcSeconds: number): string {
  if (utcSeconds === 0) return 'Unknown';
  return new Date(utcSeconds * 1000).toLocaleString();
}

/** Self-dismissing success toast pinned to the bottom of the panel. */
function SuccessToast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 4500);
    return () => clearTimeout(t);
  }, [onDismiss]);
  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[2000] bg-emerald-600 text-white text-sm px-4 py-2.5 rounded-lg shadow-2xl border border-emerald-500/40 flex items-center gap-2">
      <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
      </svg>
      {message}
      <button onClick={onDismiss} className="ml-2 text-emerald-100/80 hover:text-white text-base leading-none" aria-label="Dismiss">×</button>
    </div>
  );
}

/** Self-dismissing error toast pinned to the bottom of the panel. */
function ErrorToast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 6000);
    return () => clearTimeout(t);
  }, [onDismiss]);
  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[2000] bg-red-600 text-white text-sm px-4 py-2.5 rounded-lg shadow-2xl border border-red-500/40 flex items-center gap-2 max-w-[640px]">
      <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      </svg>
      <span className="truncate">{message}</span>
      <button onClick={onDismiss} className="ml-2 text-red-100/80 hover:text-white text-base leading-none shrink-0" aria-label="Dismiss">×</button>
    </div>
  );
}

/**
 * Read + parse a .bin file by PATH on the main process. We deliberately do
 * NOT marshal file bytes through IPC — a 100MB log used to take minutes to
 * round-trip as `number[]` (one JS Number per byte) and froze the UI the
 * whole time. Now the renderer just sends a string and gets streamed
 * progress via onLogParseProgress.
 *
 * Returns the error message on failure so the caller can surface it - the
 * main-process handler also auto-removes missing files from the recent list,
 * so a silent failure here looks like "Open just deleted the row".
 */
async function parseAndAnalyze(path: string): Promise<string | null> {
  const store = useLogStore.getState();
  // Flip parsing state on BEFORE the await so the progress UI renders
  // immediately — without this the user saw a frozen window for the read.
  store.setIsParsingLog(true);
  store.setParseProgress(0);

  try {
    const result = await window.electronAPI.logParseFile(path) as { log: unknown; healthResults: unknown[] };
    store.setCurrentLog(result.log as ReturnType<typeof useLogStore.getState>['currentLog'], path);
    store.setHealthResults(result.healthResults as ReturnType<typeof useLogStore.getState>['healthResults']);
    store.setActiveTab('report');
    return null;
  } catch (error) {
    console.error('[Logs] Parse failed:', error);
    return error instanceof Error ? error.message : String(error);
  } finally {
    store.setIsParsingLog(false);
  }
}

interface RecentLog { path: string; name: string; size: number; openedAt: number }

export function LogListPanel() {
  const availableLogs = useLogStore((s) => s.availableLogs);
  const isListLoading = useLogStore((s) => s.isListLoading);
  const downloadingLogId = useLogStore((s) => s.downloadingLogId);
  const downloadProgress = useLogStore((s) => s.downloadProgress);
  const isParsingLog = useLogStore((s) => s.isParsingLog);
  const parseProgress = useLogStore((s) => s.parseProgress);
  const isConnected = useConnectionStore((s) => s.connectionState.isConnected);
  const protocol = useConnectionStore((s) => s.connectionState.protocol);
  const isMavlink = protocol === 'mavlink';
  const [listRequested, setListRequested] = useState(false);
  const [recentLogs, setRecentLogs] = useState<RecentLog[]>([]);
  const [openingRecent, setOpeningRecent] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [errorToast, setErrorToast] = useState<string | null>(null);

  /**
   * Map of FC log ID -> recent file path for that log, derived from the
   * recently-downloaded set. Used to badge each row in the FC list with a
   * "Downloaded" indicator so the user knows which logs already exist locally.
   *
   * The convention from the main-process logDownload handler is that the
   * saved filename includes the log id (e.g. `log_3.bin`) - we extract it
   * cheaply rather than persisting a separate id mapping.
   */
  const downloadedById = useMemo(() => {
    const map = new Map<number, RecentLog>();
    for (const r of recentLogs) {
      const m = r.name.match(/log[_-]?(\d+)/i);
      if (m) {
        const id = Number(m[1]);
        if (Number.isFinite(id)) map.set(id, r);
      }
    }
    return map;
  }, [recentLogs]);

  useEffect(() => {
    window.electronAPI.logRecentGet().then(setRecentLogs);
  }, []);

  useEffect(() => {
    const cleanupProgress = window.electronAPI.onLogDownloadProgress((progress) => {
      useLogStore.getState().setDownloadProgress(
        progress.total > 0 ? (progress.received / progress.total) * 100 : 0,
      );
    });

    const cleanupComplete = window.electronAPI.onLogDownloadComplete(() => {
      useLogStore.getState().setDownloadingLogId(null);
      useLogStore.getState().setDownloadProgress(0);
    });

    const cleanupError = window.electronAPI.onLogDownloadError(() => {
      useLogStore.getState().setDownloadingLogId(null);
      useLogStore.getState().setDownloadProgress(0);
    });

    const cleanupParseProgress = window.electronAPI.onLogParseProgress((progress) => {
      useLogStore.getState().setParseProgress(
        progress.totalBytes > 0 ? (progress.bytesConsumed / progress.totalBytes) * 100 : 0,
      );
    });

    return () => {
      cleanupProgress();
      cleanupComplete();
      cleanupError();
      cleanupParseProgress();
    };
  }, []);

  const handleRefresh = async () => {
    useLogStore.getState().setIsListLoading(true);
    setListRequested(true);
    try {
      const logs = await window.electronAPI.logListRequest() as LogListEntry[];
      useLogStore.getState().setAvailableLogs(logs);
    } finally {
      useLogStore.getState().setIsListLoading(false);
    }
  };

  const handleDownload = async (log: LogListEntry) => {
    useLogStore.getState().setDownloadingLogId(log.id);
    useLogStore.getState().setDownloadProgress(0);

    const savedPath = await window.electronAPI.logDownload(log.id, log.size);
    useLogStore.getState().setDownloadingLogId(null);
    if (!savedPath) return;

    // Register in the recent-logs list so the user can re-open it without
    // hitting the FC again, and refresh the local mirror so the UI updates.
    const filename = savedPath.split(/[\\/]/).pop() ?? `log_${log.id}.bin`;
    await window.electronAPI.logRecentAdd({ path: savedPath, name: filename, size: log.size });
    const updated = await window.electronAPI.logRecentGet();
    setRecentLogs(updated);
    setToast(`Saved ${filename} (${formatBytes(log.size)})`);
  };

  const handleOpenFile = async () => {
    const picked = await window.electronAPI.logOpenDialog();
    if (!picked) return;
    const err = await parseAndAnalyze(picked.path);
    if (err) setErrorToast(err);
    window.electronAPI.logRecentGet().then(setRecentLogs);
  };

  const handleOpenRecent = async (log: RecentLog) => {
    setOpeningRecent(log.path);
    try {
      // Main-process LOG_PARSE_FILE handles both the file read + recents
      // refresh + parse. If the file is gone it throws AND removes the entry
      // from recents - surface the error so the user knows why the row
      // disappeared instead of thinking "Open" deleted it.
      const err = await parseAndAnalyze(log.path);
      if (err) setErrorToast(err);
    } finally {
      window.electronAPI.logRecentGet().then(setRecentLogs);
      setOpeningRecent(null);
    }
  };

  // Remove from recent list only — never touches the .bin on disk.
  const handleRemoveRecent = async (log: RecentLog) => {
    await window.electronAPI.logRecentRemove(log.path);
    setRecentLogs(prev => prev.filter(l => l.path !== log.path));
  };

  const handleClearRecents = async () => {
    await window.electronAPI.logRecentClear();
    setRecentLogs([]);
  };

  const handleCancel = () => {
    window.electronAPI.logDownloadCancel();
    useLogStore.getState().setDownloadingLogId(null);
    useLogStore.getState().setDownloadProgress(0);
  };

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {/* Actions */}
      <div className="flex items-center gap-3">
        {isConnected && isMavlink && (
          <button
            onClick={handleRefresh}
            disabled={isListLoading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-surface-raised disabled:text-content-secondary text-white text-sm font-medium rounded-lg transition-colors"
          >
            {isListLoading ? 'Loading...' : 'List Logs from FC'}
          </button>
        )}
        <button
          onClick={handleOpenFile}
          disabled={isParsingLog}
          className="px-4 py-2 bg-surface-raised hover:bg-surface-raised disabled:bg-surface-raised disabled:text-content-tertiary text-content text-sm font-medium rounded-lg transition-colors"
        >
          Open .bin File
        </button>
      </div>

      {/* Parse progress */}
      {isParsingLog && (
        <div className="bg-surface rounded-xl border border-subtle p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-content">Parsing log...</span>
            <span className="text-sm text-content-secondary">{parseProgress.toFixed(0)}%</span>
          </div>
          <div className="w-full bg-surface-inset rounded-full h-2">
            <div className="bg-blue-500 h-2 rounded-full transition-all" style={{ width: `${parseProgress}%` }} />
          </div>
        </div>
      )}

      {/* Not connected hint */}
      {!isConnected && availableLogs.length === 0 && recentLogs.length === 0 && !isParsingLog && (
        <div className="bg-surface rounded-xl border border-subtle p-6 text-center">
          <p className="text-content-secondary text-sm">
            Connect to a flight controller to download logs, or open a .bin file from disk.
          </p>
        </div>
      )}

      {/* Recent logs */}
      {recentLogs.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs text-content-secondary uppercase tracking-wider">Recent Logs</div>
            <button
              onClick={handleClearRecents}
              disabled={openingRecent !== null}
              title="Clear list (files stay on disk)"
              className="text-xs text-content-tertiary hover:text-red-400 disabled:opacity-50 transition-colors"
            >
              Clear all
            </button>
          </div>
          <div className="bg-surface rounded-xl border border-subtle overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-subtle">
                  <th className="text-left px-4 py-2.5 text-content-secondary font-medium">File</th>
                  <th className="text-right px-4 py-2.5 text-content-secondary font-medium">Size</th>
                  <th className="text-right px-4 py-2.5 text-content-secondary font-medium">Opened</th>
                  <th className="text-right px-4 py-2.5 text-content-secondary font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {recentLogs.map((log) => (
                  <tr key={log.path} className="border-b border-subtle hover:bg-surface-overlay-subtle">
                    <td className="px-4 py-2.5">
                      <div className="text-content truncate max-w-[240px]" title={log.path}>{log.name}</div>
                      <div className="text-[11px] text-content-tertiary truncate max-w-[240px]" title={log.path}>
                        {log.path.split(/[\\/]/).slice(0, -1).join('/')}
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-content-secondary text-right whitespace-nowrap">{formatBytes(log.size)}</td>
                    <td className="px-4 py-2.5 text-content-secondary text-right whitespace-nowrap text-xs">
                      {new Date(log.openedAt).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleOpenRecent(log)}
                          disabled={isParsingLog || openingRecent !== null}
                          className="text-xs px-3 py-1 bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 disabled:opacity-50 rounded-md transition-colors"
                        >
                          {openingRecent === log.path ? 'Opening...' : 'Open'}
                        </button>
                        <button
                          onClick={() => handleRemoveRecent(log)}
                          disabled={openingRecent !== null}
                          title="Remove from recent list (file stays on disk)"
                          aria-label={`Remove ${log.name} from recent list`}
                          className="text-xs w-7 h-7 inline-flex items-center justify-center text-content-tertiary hover:text-red-400 hover:bg-red-500/10 disabled:opacity-50 rounded-md transition-colors"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Success toast (download complete) */}
      {toast && <SuccessToast message={toast} onDismiss={() => setToast(null)} />}

      {/* Error toast (parse failed - usually missing file) */}
      {errorToast && <ErrorToast message={errorToast} onDismiss={() => setErrorToast(null)} />}

      {/* No logs found after request */}
      {listRequested && !isListLoading && availableLogs.length === 0 && (
        <div className="bg-surface rounded-xl border border-amber-500/30 p-6 text-center">
          <p className="text-amber-400 text-sm font-medium mb-1">No logs found</p>
          <p className="text-content-secondary text-xs">
            The flight controller did not return any logs. This can happen if no flights have been recorded or the FC timed out.
          </p>
        </div>
      )}

      {/* Log list */}
      {availableLogs.length > 0 && (
        <div className="bg-surface rounded-xl border border-subtle overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-subtle">
                <th className="text-left px-4 py-3 text-content-secondary font-medium">#</th>
                <th className="text-left px-4 py-3 text-content-secondary font-medium">Date</th>
                <th className="text-right px-4 py-3 text-content-secondary font-medium">Size</th>
                <th className="text-right px-4 py-3 text-content-secondary font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {availableLogs.map((log) => {
                const downloaded = downloadedById.get(log.id) ?? null;
                return (
                  <tr key={log.id} className="border-b border-subtle hover:bg-surface-overlay-subtle">
                    <td className="px-4 py-3 text-content">
                      <div className="flex items-center gap-2">
                        <span>{log.id}</span>
                        {downloaded && (
                          <span
                            title={`Already downloaded:\n${downloaded.path}`}
                            className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                          >
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                            Downloaded
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-content">{formatDate(log.timeUtc)}</td>
                    <td className="px-4 py-3 text-content-secondary text-right">{formatBytes(log.size)}</td>
                    <td className="px-4 py-3 text-right">
                      {downloadingLogId === log.id ? (
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-24 bg-surface-inset rounded-full h-1.5">
                            <div className="bg-blue-500 h-1.5 rounded-full transition-all" style={{ width: `${downloadProgress}%` }} />
                          </div>
                          <button onClick={handleCancel} className="text-xs text-red-400 hover:text-red-300">
                            Cancel
                          </button>
                        </div>
                      ) : downloaded ? (
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => handleOpenRecent(downloaded)}
                            disabled={isParsingLog || openingRecent !== null}
                            className="text-xs px-3 py-1 bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30 disabled:opacity-50 rounded-md transition-colors"
                          >
                            {openingRecent === downloaded.path ? 'Opening...' : 'Open'}
                          </button>
                          <button
                            onClick={() => handleDownload(log)}
                            disabled={downloadingLogId !== null}
                            title="Re-download from FC"
                            className="text-xs px-2 py-1 text-content-secondary hover:text-content disabled:opacity-50 rounded-md transition-colors"
                          >
                            ↻
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleDownload(log)}
                          disabled={downloadingLogId !== null}
                          className="text-xs px-3 py-1 bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 disabled:opacity-50 rounded-md transition-colors"
                        >
                          Download
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
