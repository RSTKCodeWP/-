/**
 * FilesTab — MAVLink-FTP file browser for the connected flight controller.
 *
 * Browse, download, upload, delete, and rename files on the FC's virtual
 * filesystem. All ops route through the IPC handlers in main/ipc-handlers.ts
 * which share the transient FtpClient pattern (build → swap into the global
 * slot so FILE_TRANSFER_PROTOCOL responses route correctly → restore).
 *
 * SITL note: ArduPilot SITL exposes the FTP-virtual /APM/ tree, NOT the
 * host-side <cwd>/scripts/ folder where SITL actually loads scripts from.
 * The browser shows the FTP view (matching real-hardware behaviour) and
 * surfaces a banner explaining the divergence when running on SITL.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  FolderOpen,
  Folder,
  File,
  ChevronRight,
  Home,
  RefreshCw,
  Download,
  Upload,
  Trash2,
  Pencil,
  Loader2,
  AlertCircle,
  X,
} from 'lucide-react';
import { useConnectionStore } from '../../stores/connection-store';

interface DirEntry {
  kind: 'dir' | 'file';
  name: string;
  size?: number;
}

type RowBusy = { state: 'downloading' | 'done' | 'error' | 'deleting' | 'renaming'; detail?: string };

const DEFAULT_PATH = '/';

export const FilesTab: React.FC = () => {
  const isConnected = useConnectionStore((s) => s.connectionState.isConnected);
  const protocol = useConnectionStore((s) => s.connectionState.protocol);
  const isSitl = useConnectionStore((s) => s.connectionState.isSitl);

  const [path, setPath] = useState<string>(DEFAULT_PATH);
  const [entries, setEntries] = useState<DirEntry[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Per-row inline status keyed by the FC-side full path.
  const [rowState, setRowState] = useState<Record<string, RowBusy>>({});

  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Modal state for delete confirmation and rename input.
  const [confirmDelete, setConfirmDelete] = useState<DirEntry | null>(null);
  const [renameTarget, setRenameTarget] = useState<DirEntry | null>(null);

  const refresh = useCallback(async (target: string) => {
    setLoading(true);
    setError(null);
    setEntries(null);
    const result = await window.electronAPI.mavlinkFtpList(target);
    setLoading(false);
    if (!result.success || !result.entries) {
      setError(result.error ?? 'Unknown error');
      return;
    }
    const sorted = [...result.entries].sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === 'dir' ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    setEntries(sorted);
  }, []);

  useEffect(() => {
    if (isConnected && protocol === 'mavlink') {
      void refresh(path);
    }
  }, [isConnected, protocol, path, refresh]);

  const fcPathFor = useCallback((entry: DirEntry) =>
    path.endsWith('/') ? `${path}${entry.name}` : `${path}/${entry.name}`,
  [path]);

  const handleEntryClick = useCallback((entry: DirEntry) => {
    if (entry.kind !== 'dir') return;
    // Always navigate into directories with a trailing slash. ArduPilot's
    // SITL POSIX backend prefix-matches its virtual mounts ("/APM/", "/@SYS/"…)
    // and NAKs the bare "/APM" form; ChibiOS accepts either, so the slash
    // form is the safe common denominator.
    setPath(`${fcPathFor(entry)}/`);
  }, [fcPathFor]);

  const handleDownload = useCallback(async (entry: DirEntry) => {
    if (entry.kind !== 'file') return;
    const fcPath = fcPathFor(entry);
    setRowState(d => ({ ...d, [fcPath]: { state: 'downloading' } }));
    const result = await window.electronAPI.mavlinkFtpDownload(fcPath);
    setRowState(d => ({
      ...d,
      [fcPath]: result.success
        ? { state: 'done', detail: result.savedTo }
        : { state: 'error', detail: result.error },
    }));
  }, [fcPathFor]);

  const handleUpload = useCallback(async () => {
    setUploading(true);
    setUploadError(null);
    const result = await window.electronAPI.mavlinkFtpUpload(path);
    setUploading(false);
    if (result.cancelled) return;
    if (!result.success) {
      setUploadError(result.error ?? 'Upload failed');
      return;
    }
    void refresh(path);
  }, [path, refresh]);

  const handleConfirmDelete = useCallback(async () => {
    const entry = confirmDelete;
    if (!entry) return;
    const fcPath = fcPathFor(entry);
    setConfirmDelete(null);
    setRowState(d => ({ ...d, [fcPath]: { state: 'deleting' } }));
    const result = await window.electronAPI.mavlinkFtpDelete(fcPath, entry.kind);
    if (!result.success) {
      setRowState(d => ({ ...d, [fcPath]: { state: 'error', detail: result.error } }));
      return;
    }
    setRowState(d => {
      const next = { ...d };
      delete next[fcPath];
      return next;
    });
    void refresh(path);
  }, [confirmDelete, fcPathFor, path, refresh]);

  const handleRenameSubmit = useCallback(async (newName: string) => {
    const entry = renameTarget;
    if (!entry) return;
    const trimmed = newName.trim();
    if (!trimmed || trimmed === entry.name) {
      setRenameTarget(null);
      return;
    }
    if (trimmed.includes('/')) {
      setRowState(d => ({ ...d, [fcPathFor(entry)]: { state: 'error', detail: 'Name cannot contain "/"' } }));
      setRenameTarget(null);
      return;
    }
    const oldPath = fcPathFor(entry);
    const newPath = path.endsWith('/') ? `${path}${trimmed}` : `${path}/${trimmed}`;
    setRenameTarget(null);
    setRowState(d => ({ ...d, [oldPath]: { state: 'renaming' } }));
    const result = await window.electronAPI.mavlinkFtpRename(oldPath, newPath);
    if (!result.success) {
      setRowState(d => ({ ...d, [oldPath]: { state: 'error', detail: result.error } }));
      return;
    }
    setRowState(d => {
      const next = { ...d };
      delete next[oldPath];
      return next;
    });
    void refresh(path);
  }, [renameTarget, fcPathFor, path, refresh]);

  if (!isConnected) {
    return (
      <ChromedShell>
        <EmptyState
          title="Not connected"
          message="Connect to a flight controller to browse its filesystem."
        />
      </ChromedShell>
    );
  }

  if (protocol !== 'mavlink') {
    return (
      <ChromedShell>
        <EmptyState
          title="MAVLink only"
          message="The FC file browser uses MAVLink-FTP. It is not available on MSP / iNav connections."
        />
      </ChromedShell>
    );
  }

  return (
    <ChromedShell>
      {isSitl && (
        <div className="mb-3 px-3 py-2 rounded text-xs bg-blue-500/10 border border-blue-500/30 text-blue-400">
          <div className="font-semibold mb-0.5">SITL note</div>
          ArduPilot SITL exposes the FTP-virtual <code className="font-mono text-[11px]">/APM/</code> tree. Files SITL actually loads (e.g. scripts) live on the host disk under the SITL working directory. They may not match what is shown here.
        </div>
      )}

      <PathBar
        path={path}
        loading={loading}
        uploading={uploading}
        onNavigate={setPath}
        onRefresh={() => refresh(path)}
        onUpload={handleUpload}
      />

      {uploadError && (
        <div className="mt-2 flex items-start gap-2 px-3 py-2 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div>
            <div className="font-semibold mb-0.5">Upload failed</div>
            <div>{uploadError}</div>
          </div>
          <button onClick={() => setUploadError(null)} className="ml-auto text-content-secondary hover:text-content">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {error && (
        <div className="mt-3 flex items-start gap-2 px-3 py-2 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div>
            <div className="font-semibold mb-0.5">Could not list {path}</div>
            <div>{error}</div>
          </div>
        </div>
      )}

      {!error && entries !== null && entries.length === 0 && !loading && (
        <div className="mt-6 text-center text-sm text-content-secondary">Directory is empty.</div>
      )}

      {entries !== null && entries.length > 0 && (
        <div className="mt-3 rounded-lg border border-default bg-surface overflow-hidden">
          <div className="grid grid-cols-[1fr_100px_180px] text-[10px] font-semibold tracking-wider text-content-secondary uppercase border-b border-default px-3 py-2">
            <div>Name</div>
            <div className="text-right">Size</div>
            <div className="text-right">Actions</div>
          </div>
          <div className="max-h-[60vh] overflow-y-auto">
            {entries.map(entry => {
              const fcPath = fcPathFor(entry);
              const busy = rowState[fcPath];
              return (
                <div
                  key={entry.name}
                  className="grid grid-cols-[1fr_100px_180px] items-center px-3 py-2 text-xs border-b border-subtle last:border-b-0 hover:bg-surface-raised/40"
                >
                  <button
                    onClick={() => handleEntryClick(entry)}
                    disabled={entry.kind !== 'dir'}
                    className={`flex items-center gap-2 text-left truncate ${
                      entry.kind === 'dir' ? 'text-content hover:text-blue-400 cursor-pointer' : 'text-content-secondary cursor-default'
                    }`}
                  >
                    {entry.kind === 'dir'
                      ? <Folder className="w-4 h-4 text-amber-400 flex-shrink-0" />
                      : <File   className="w-4 h-4 text-content-tertiary flex-shrink-0" />}
                    <span className="font-mono truncate">{entry.name}</span>
                  </button>
                  <div className="text-right font-mono text-content-secondary">
                    {entry.kind === 'file' ? formatSize(entry.size ?? 0) : '—'}
                  </div>
                  <RowActions
                    entry={entry}
                    busy={busy}
                    onDownload={() => handleDownload(entry)}
                    onRename={() => setRenameTarget(entry)}
                    onDelete={() => setConfirmDelete(entry)}
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {confirmDelete && (
        <ConfirmDeleteModal
          entry={confirmDelete}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={handleConfirmDelete}
        />
      )}

      {renameTarget && (
        <RenameModal
          entry={renameTarget}
          onCancel={() => setRenameTarget(null)}
          onSubmit={handleRenameSubmit}
        />
      )}
    </ChromedShell>
  );
};

function ChromedShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-full flex flex-col p-4 gap-3 overflow-y-auto">
      <div className="flex items-center gap-3 flex-shrink-0">
        <FolderOpen className="w-6 h-6 text-content-secondary" />
        <div>
          <h2 className="text-lg font-semibold text-content">FC Files</h2>
          <p className="text-xs text-content-secondary">Browse, download, upload, and manage files on the flight controller via MAVLink-FTP.</p>
        </div>
      </div>
      {children}
    </div>
  );
}

function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="max-w-md text-center">
        <div className="text-content font-medium mb-1">{title}</div>
        <div className="text-sm text-content-secondary">{message}</div>
      </div>
    </div>
  );
}

interface PathBarProps {
  path: string;
  loading: boolean;
  uploading: boolean;
  onNavigate: (path: string) => void;
  onRefresh: () => void;
  onUpload: () => void;
}

function PathBar({ path, loading, uploading, onNavigate, onRefresh, onUpload }: PathBarProps) {
  const parts = path.split('/').filter(Boolean);
  return (
    <div className="flex items-center gap-1 flex-wrap text-xs" data-tour="ftp-path-bar">
      <button
        onClick={() => onNavigate('/')}
        className="flex items-center gap-1 px-2 py-1 rounded hover:bg-surface-raised text-content-secondary hover:text-content"
        title="Go to root"
      >
        <Home className="w-3.5 h-3.5" />
      </button>
      {parts.map((part, i) => {
        const targetPath = '/' + parts.slice(0, i + 1).join('/') + '/';
        const isLast = i === parts.length - 1;
        return (
          <React.Fragment key={`${i}-${part}`}>
            <ChevronRight className="w-3 h-3 text-content-tertiary" />
            <button
              onClick={() => onNavigate(targetPath)}
              className={`px-2 py-1 rounded font-mono ${
                isLast
                  ? 'text-content font-medium cursor-default'
                  : 'text-content-secondary hover:bg-surface-raised hover:text-content'
              }`}
              disabled={isLast}
            >
              {part}
            </button>
          </React.Fragment>
        );
      })}
      <div className="flex-1" />
      <button
        data-tour="ftp-upload-button"
        onClick={onUpload}
        disabled={uploading}
        className="flex items-center gap-1 px-2 py-1 rounded text-content hover:bg-surface-raised disabled:opacity-50"
        title="Upload file to this directory"
      >
        {uploading
          ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
          : <Upload className="w-3.5 h-3.5" />}
        <span>{uploading ? 'Uploading…' : 'Upload'}</span>
      </button>
      <button
        onClick={onRefresh}
        disabled={loading}
        className="flex items-center gap-1 px-2 py-1 rounded hover:bg-surface-raised text-content-secondary hover:text-content disabled:opacity-50"
        title="Refresh listing"
      >
        {loading
          ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
          : <RefreshCw className="w-3.5 h-3.5" />}
      </button>
    </div>
  );
}

function RowActions({
  entry,
  busy,
  onDownload,
  onRename,
  onDelete,
}: {
  entry: DirEntry;
  busy: RowBusy | undefined;
  onDownload: () => void;
  onRename: () => void;
  onDelete: () => void;
}) {
  if (busy?.state === 'downloading') {
    return <BusyChip icon={<Loader2 className="w-3 h-3 animate-spin" />} label="Downloading…" />;
  }
  if (busy?.state === 'deleting') {
    return <BusyChip icon={<Loader2 className="w-3 h-3 animate-spin" />} label="Deleting…" />;
  }
  if (busy?.state === 'renaming') {
    return <BusyChip icon={<Loader2 className="w-3 h-3 animate-spin" />} label="Renaming…" />;
  }
  if (busy?.state === 'error') {
    return (
      <div className="flex items-center justify-end gap-2">
        <span className="text-rose-400 text-[11px] truncate" title={busy.detail ?? 'Failed'}>Failed</span>
        <IconAction title="Rename" onClick={onRename}><Pencil className="w-3 h-3" /></IconAction>
        <IconAction title="Delete" onClick={onDelete} variant="danger"><Trash2 className="w-3 h-3" /></IconAction>
        {entry.kind === 'file' && (
          <IconAction title="Download" onClick={onDownload}><Download className="w-3 h-3" /></IconAction>
        )}
      </div>
    );
  }
  if (busy?.state === 'done' && entry.kind === 'file') {
    return (
      <div className="flex items-center justify-end gap-2">
        <span className="text-emerald-400 text-[11px] truncate" title={`Saved to ${busy.detail}`}>Saved</span>
        <IconAction title="Rename" onClick={onRename}><Pencil className="w-3 h-3" /></IconAction>
        <IconAction title="Delete" onClick={onDelete} variant="danger"><Trash2 className="w-3 h-3" /></IconAction>
        <IconAction title="Re-download" onClick={onDownload}><Download className="w-3 h-3" /></IconAction>
      </div>
    );
  }
  return (
    <div className="flex items-center justify-end gap-2" data-tour="ftp-row-actions">
      <IconAction title="Rename" onClick={onRename}><Pencil className="w-3 h-3" /></IconAction>
      <IconAction title="Delete" onClick={onDelete} variant="danger"><Trash2 className="w-3 h-3" /></IconAction>
      {entry.kind === 'file' && (
        <IconAction title="Download" onClick={onDownload}><Download className="w-3 h-3" /></IconAction>
      )}
    </div>
  );
}

function BusyChip({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <span className="flex items-center justify-end gap-1 text-content-secondary text-[11px]">
      {icon}
      {label}
    </span>
  );
}

function IconAction({
  title,
  onClick,
  variant,
  children,
}: {
  title: string;
  onClick: () => void;
  variant?: 'danger';
  children: React.ReactNode;
}) {
  const danger = variant === 'danger';
  return (
    <button
      onClick={onClick}
      title={title}
      aria-label={title}
      className={`p-1 rounded ${
        danger
          ? 'text-rose-400 hover:bg-rose-500/10 hover:text-rose-300'
          : 'text-content-secondary hover:bg-surface-raised hover:text-content'
      }`}
    >
      {children}
    </button>
  );
}

function ConfirmDeleteModal({
  entry,
  onCancel,
  onConfirm,
}: {
  entry: DirEntry;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <ModalShell onCancel={onCancel}>
      <div className="text-content font-medium mb-1">Delete {entry.kind === 'dir' ? 'directory' : 'file'}?</div>
      <div className="text-xs text-content-secondary mb-4 break-all">
        <span className="font-mono">{entry.name}</span> will be removed from the flight controller. This cannot be undone.
        {entry.kind === 'dir' && (
          <span className="block mt-1 text-amber-400">Directories must be empty - non-empty directories will be rejected by the FC.</span>
        )}
      </div>
      <div className="flex justify-end gap-2">
        <button
          onClick={onCancel}
          className="px-3 py-1.5 rounded text-xs text-content hover:bg-surface-raised"
        >
          Cancel
        </button>
        <button
          onClick={onConfirm}
          className="px-3 py-1.5 rounded text-xs bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/30"
        >
          Delete
        </button>
      </div>
    </ModalShell>
  );
}

function RenameModal({
  entry,
  onCancel,
  onSubmit,
}: {
  entry: DirEntry;
  onCancel: () => void;
  onSubmit: (newName: string) => void;
}) {
  const [name, setName] = useState(entry.name);
  return (
    <ModalShell onCancel={onCancel}>
      <div className="text-content font-medium mb-1">Rename {entry.kind === 'dir' ? 'directory' : 'file'}</div>
      <div className="text-xs text-content-secondary mb-3 break-all">
        Current name: <span className="font-mono">{entry.name}</span>
      </div>
      <input
        type="text"
        value={name}
        onChange={e => setName(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter') onSubmit(name);
          if (e.key === 'Escape') onCancel();
        }}
        autoFocus
        className="w-full px-2 py-1.5 mb-4 rounded bg-surface-raised border border-default text-content text-xs font-mono focus:outline-none focus:border-blue-500/60"
        placeholder="new name"
      />
      <div className="flex justify-end gap-2">
        <button
          onClick={onCancel}
          className="px-3 py-1.5 rounded text-xs text-content hover:bg-surface-raised"
        >
          Cancel
        </button>
        <button
          onClick={() => onSubmit(name)}
          disabled={!name.trim() || name.trim() === entry.name}
          className="px-3 py-1.5 rounded text-xs bg-blue-500/20 hover:bg-blue-500/30 text-blue-300 border border-blue-500/30 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Rename
        </button>
      </div>
    </ModalShell>
  );
}

function ModalShell({ children, onCancel }: { children: React.ReactNode; onCancel: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onCancel}
    >
      <div
        className="bg-surface border border-default rounded-lg p-5 max-w-md w-full mx-4 shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
