import { useEffect, useState, useRef } from 'react';
import { useModuleStore } from '../../stores/module-store';
import type { ModuleProgress, InstalledModule } from '../../../shared/module-types';

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function PackageIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
    </svg>
  );
}

function KeyIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  );
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  );
}

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function AlertIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
  );
}

function ArrowUpIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 10l7-7m0 0l7 7m-7-7v18" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// License Type Badge
// ---------------------------------------------------------------------------

function LicenseTypeBadge({ type }: { type: InstalledModule['licenseType'] }) {
  const styles = {
    perpetual: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    subscription: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    trial: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  };

  const labels = {
    perpetual: 'Perpetual',
    subscription: 'Subscription',
    trial: 'Trial',
  };

  return (
    <span className={`px-2 py-0.5 text-xs rounded-full border ${styles[type]}`}>
      {labels[type]}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Progress Indicator
// ---------------------------------------------------------------------------

function ActivationProgress({ progress }: { progress: ModuleProgress }) {
  const stageLabels: Record<ModuleProgress['stage'], string> = {
    validating: 'Validating',
    activating: 'Activating',
    downloading: 'Downloading',
    verifying: 'Verifying',
    complete: 'Complete',
    error: 'Error',
  };

  const stageColors: Record<ModuleProgress['stage'], string> = {
    validating: 'text-blue-400',
    activating: 'text-blue-400',
    downloading: 'text-blue-400',
    verifying: 'text-blue-400',
    complete: 'text-emerald-400',
    error: 'text-red-400',
  };

  return (
    <div className="bg-surface rounded-xl border border-subtle p-5">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
          {progress.stage === 'complete' ? (
            <CheckCircleIcon className="w-5 h-5 text-emerald-400" />
          ) : progress.stage === 'error' ? (
            <AlertIcon className="w-5 h-5 text-red-400" />
          ) : (
            <div className="w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          )}
        </div>
        <div>
          <h3 className={`text-sm font-medium ${stageColors[progress.stage]}`}>
            {stageLabels[progress.stage]}
          </h3>
          <p className="text-xs text-content-secondary">{progress.message}</p>
        </div>
      </div>

      {/* Progress bar */}
      {progress.percent !== undefined && progress.stage !== 'error' && (
        <div className="w-full h-1.5 bg-surface-inset rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${
              progress.stage === 'complete' ? 'bg-emerald-500' : 'bg-blue-500'
            }`}
            style={{ width: `${progress.percent}%` }}
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Module Card
// ---------------------------------------------------------------------------

function ModuleCard({
  module,
  hasUpdate,
  isUpdating,
  onUpdate,
  onRemove,
  onToggle,
}: {
  module: InstalledModule;
  hasUpdate: boolean;
  isUpdating: boolean;
  onUpdate: () => void;
  onRemove: () => void;
  onToggle: (enabled: boolean) => void;
}) {
  const [confirmRemove, setConfirmRemove] = useState(false);
  const isEnabled = module.enabled !== false;

  const displayName = module.name
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');

  return (
    <div className="flex items-center gap-3 px-4 py-3">
      {/* Icon */}
      <div
        className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 transition-colors ${
          isEnabled
            ? 'bg-purple-500/10 border border-purple-500/20'
            : 'bg-surface-raised border border-subtle'
        }`}
      >
        <PackageIcon className={`w-5 h-5 ${isEnabled ? 'text-purple-400' : 'text-content-tertiary'}`} />
      </div>

      {/* Info */}
      <div className={`flex-1 min-w-0 ${isEnabled ? '' : 'opacity-60'}`}>
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-content truncate">{displayName}</h3>
          <span className="text-xs text-content-tertiary shrink-0">v{module.version}</span>
          {hasUpdate && (
            <button
              onClick={onUpdate}
              disabled={isUpdating}
              className={`flex items-center gap-1 px-1.5 py-0.5 text-[10px] rounded-full border transition-colors shrink-0 ${
                isUpdating
                  ? 'bg-blue-500/10 text-blue-400/60 border-blue-500/20 cursor-wait'
                  : 'bg-blue-500/10 text-blue-400 border-blue-500/20 hover:bg-blue-500/20 hover:text-blue-300'
              }`}
              data-tip="Download and install the latest version"
            >
              {isUpdating ? (
                <span className="w-2.5 h-2.5 rounded-full border border-blue-400/30 border-t-blue-400 animate-spin" />
              ) : (
                <ArrowUpIcon className="w-2.5 h-2.5" />
              )}
              {isUpdating ? 'Updating...' : 'Update'}
            </button>
          )}
        </div>
        <p className="text-xs text-content-secondary font-mono mt-0.5 truncate">{module.slug}</p>
      </div>

      {/* License + controls */}
      <div className={`shrink-0 ${isEnabled ? '' : 'opacity-60'}`}>
        <LicenseTypeBadge type={module.licenseType} />
      </div>
      <div className="shrink-0 flex items-center gap-1 pl-2 border-l border-subtle">
        <button
          onClick={() => onToggle(!isEnabled)}
          role="switch"
          aria-checked={isEnabled}
          data-tip={isEnabled ? 'Turn off (stays on board)' : 'Turn on'}
          className={`relative w-9 h-5 rounded-full transition-colors ${
            isEnabled ? 'bg-emerald-500' : 'bg-surface-inset border border-subtle'
          }`}
        >
          <span
            className={`absolute left-0 top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
              isEnabled ? 'translate-x-[18px]' : 'translate-x-0.5'
            }`}
          />
        </button>
        {confirmRemove ? (
          <div className="flex items-center gap-1 ml-1">
            <button
              onClick={() => {
                onRemove();
                setConfirmRemove(false);
              }}
              className="px-2 py-1 text-xs bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors"
            >
              Confirm
            </button>
            <button
              onClick={() => setConfirmRemove(false)}
              className="px-2 py-1 text-xs bg-surface-raised text-content-secondary rounded transition-colors"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirmRemove(true)}
            className="p-1.5 ml-1 rounded-lg text-content-tertiary hover:text-red-400 hover:bg-red-500/10 transition-colors"
            data-tip="Remove cargo"
          >
            <TrashIcon className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty State
// ---------------------------------------------------------------------------

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <div className="w-16 h-16 rounded-2xl bg-surface border border-subtle flex items-center justify-center mb-5">
        <PackageIcon className="w-8 h-8 text-content-tertiary" />
      </div>
      <h3 className="text-lg font-medium text-content mb-2">No cargo on board</h3>
      <p className="text-sm text-content-secondary max-w-sm leading-relaxed">
        Have a cargo key? Enter it above and the rest happens on its own.
        Keys start finding their way out when the Hangar opens.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main View
// ---------------------------------------------------------------------------

export function ModuleManagerView() {
  const {
    modules,
    isLoading,
    error,
    activating,
    progress,
    updates,
    updating,
    checkingUpdates,
    updatesCheckedAt,
    updatesError,
    loadModules,
    activateLicense,
    removeLicense,
    checkUpdates,
    updateModule,
    updateAll,
    setEnabled,
    setProgress,
    clearError,
  } = useModuleStore();

  const [keyInput, setKeyInput] = useState('');
  const [restartRequired, setRestartRequired] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load modules and check for updates on mount
  useEffect(() => {
    loadModules();
    checkUpdates();
  }, [loadModules, checkUpdates]);

  // Subscribe to progress events from main process
  useEffect(() => {
    const cleanup = window.electronAPI.onModuleProgress((p) => {
      setProgress(p);
    });
    return () => { cleanup(); };
  }, [setProgress]);

  const handleActivate = async () => {
    const trimmed = keyInput.trim();
    if (!trimmed) return;

    clearError();
    const result = await activateLicense(trimmed);
    if (result.success) {
      setKeyInput('');
      // Newly installed modules are only loaded into the running app at
      // startup, so the module won't appear until ArduDeck restarts.
      setRestartRequired(true);
      // Refresh updates
      checkUpdates();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleActivate();
    }
  };

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text.trim()) {
        setKeyInput(text.trim());
      }
    } catch {
      // Clipboard access denied
    }
  };

  // Group modules by license key for display
  const updateSlugs = new Set(updates.map((u) => u.slug));

  const handleToggle = async (mod: InstalledModule, enabled: boolean) => {
    const result = await setEnabled(mod.slug, enabled);
    // Bundle cargo only loads/unloads at startup; activatable cargo flips its
    // capability gate reactively and needs no restart.
    if (result.success && !mod.activatable) setRestartRequired(true);
  };

  const handleUpdate = async (slug: string) => {
    clearError();
    const result = await updateModule(slug);
    // Updated code only loads at startup, same as a fresh install.
    if (result.success) setRestartRequired(true);
  };

  const handleUpdateAll = async () => {
    clearError();
    const succeeded = await updateAll();
    if (succeeded > 0) setRestartRequired(true);
  };

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-3xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
            <PackageIcon className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-content">Cargo Bay</h1>
            <p className="text-sm text-content-secondary">Load cargo and manage what's on board</p>
          </div>
        </div>

        {/* Hangar preview banner */}
        <div className="card border-amber-500/30">
          <div className="card-body flex items-center gap-3 py-3">
            <span className="shrink-0 rounded-full bg-amber-500/15 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-amber-500">
              Coming soon
            </span>
            <p className="text-sm text-content-secondary">
              The Hangar doors open soon. What's being built inside stays under
              wraps for now. Everything here is experimental and may change
              between releases.
            </p>
          </div>
        </div>

        {/* Module key input */}
        <div className="card">
          <div className="card-header">
            <h2 className="text-sm font-medium text-content flex items-center gap-2">
              <KeyIcon className="w-4 h-4 text-blue-400" />
              Load cargo
            </h2>
          </div>
          <div className="card-body flex gap-2">
            <div className="flex-1 relative">
              <input
                ref={inputRef}
                type="text"
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="ARDUDECK.xxxxxxxx.xxxxxxxx"
                disabled={activating}
                className="w-full px-3 py-2.5 bg-surface-input border border-subtle rounded-lg text-sm text-content placeholder-content-tertiary focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 disabled:opacity-50 font-mono"
                spellCheck={false}
                autoComplete="off"
              />
              {!keyInput && (
                <button
                  onClick={handlePaste}
                  className="absolute right-2 top-1/2 -translate-y-1/2 px-2 py-1 text-xs text-content-secondary hover:text-content bg-surface-raised rounded transition-colors"
                >
                  Paste
                </button>
              )}
            </div>
            <button
              onClick={handleActivate}
              disabled={!keyInput.trim() || activating}
              className="btn btn-primary text-sm shrink-0"
            >
              {activating ? 'Adding…' : 'Add'}
            </button>
          </div>

          {/* Error message */}
          {error && (
            <div className="mx-4 mb-4 flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
              <AlertIcon className="w-4 h-4 text-red-400 shrink-0" />
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}
        </div>

        {/* Progress indicator */}
        {progress && progress.stage !== 'complete' && (
          <ActivationProgress progress={progress} />
        )}

        {/* Restart-required banner - modules only load at startup, so a freshly
            installed module stays hidden until the app restarts. */}
        {restartRequired && (
          <div className="card border-amber-500/30">
            <div className="card-body flex items-center gap-4 py-3">
              <AlertIcon className="w-5 h-5 text-amber-500 shrink-0" />
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-medium text-content">Restart required</h3>
                <p className="text-sm text-content-secondary mt-0.5">
                  Cargo changed. ArduDeck must restart for it to take effect.
                </p>
              </div>
              <button
                onClick={() => window.electronAPI.relaunchApp()}
                className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-black text-sm font-medium rounded-lg transition-colors shrink-0"
              >
                Restart now
              </button>
              <button
                onClick={() => setRestartRequired(false)}
                className="px-3 py-2 text-sm text-content-secondary hover:text-content transition-colors shrink-0"
              >
                Later
              </button>
            </div>
          </div>
        )}

        {/* On board */}
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h2 className="text-sm font-medium text-content flex items-center gap-2">
              <PackageIcon className="w-4 h-4 text-purple-400" />
              On board
              {modules.length > 0 && (
                <span className="text-xs text-content-secondary">({modules.length})</span>
              )}
            </h2>
            {modules.length > 0 && (
              <div className="flex items-center gap-2">
                {updatesError ? (
                  <span className="text-xs text-red-400" data-tip={updatesError}>
                    Check failed
                  </span>
                ) : updatesCheckedAt && !checkingUpdates && updates.length === 0 ? (
                  <span className="text-xs text-content-secondary">Up to date</span>
                ) : null}
                <button
                  onClick={() => checkUpdates()}
                  disabled={checkingUpdates}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-content-secondary hover:text-content bg-surface-raised border border-subtle rounded-lg transition-colors disabled:opacity-60"
                >
                  <RefreshIcon className={`w-3.5 h-3.5 ${checkingUpdates ? 'animate-spin' : ''}`} />
                  {checkingUpdates ? 'Checking…' : 'Check updates'}
                </button>
              </div>
            )}
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : modules.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="divide-y divide-subtle">
              {modules.map((mod) => (
                <ModuleCard
                  key={mod.slug}
                  module={mod}
                  hasUpdate={updateSlugs.has(mod.slug)}
                  isUpdating={updating === mod.slug || updating === 'all'}
                  onUpdate={() => handleUpdate(mod.slug)}
                  onRemove={() => removeLicense(mod.licenseKey)}
                  onToggle={(enabled) => handleToggle(mod, enabled)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Updates available */}
        {updates.length > 0 && (
          <div className="card border-blue-500/20">
            <div className="card-header flex items-center gap-3">
              <h3 className="text-sm font-medium text-content flex items-center gap-2">
                <ArrowUpIcon className="w-4 h-4 text-blue-400" />
                {updates.length} update{updates.length > 1 ? 's' : ''} available
              </h3>
              <div className="flex-1" />
              <button
                onClick={handleUpdateAll}
                disabled={updating !== null}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                  updating !== null
                    ? 'bg-blue-600/40 text-white/60 cursor-wait'
                    : 'bg-blue-600 hover:bg-blue-500 text-white'
                }`}
              >
                {updating === 'all' ? 'Updating all...' : updates.length > 1 ? 'Update all' : 'Update'}
              </button>
            </div>
            <div className="card-body space-y-2">
              {updates.map((u) => (
                <div key={u.slug} className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-content">{u.name}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-content-secondary">
                      {u.currentVersion} → <span className="text-blue-400">{u.latestVersion}</span>
                    </span>
                    <button
                      onClick={() => handleUpdate(u.slug)}
                      disabled={updating !== null}
                      className={`px-2 py-1 text-[11px] rounded-md border transition-colors ${
                        updating !== null
                          ? 'text-blue-400/50 border-blue-500/20 cursor-wait'
                          : 'text-blue-400 border-blue-500/30 hover:bg-blue-500/10 hover:text-blue-300'
                      }`}
                    >
                      {updating === u.slug ? 'Updating...' : 'Update'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
