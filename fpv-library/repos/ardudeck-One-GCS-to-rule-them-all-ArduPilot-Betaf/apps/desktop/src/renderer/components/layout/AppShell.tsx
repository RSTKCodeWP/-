import { type ReactNode, useEffect, useState } from 'react';
import { useConnectionStore } from '../../stores/connection-store';
import { useActiveVehicleStore } from '../../stores/active-vehicle-store';
import { useUpdateStore } from '../../stores/update-store';
import { useNavigationStore } from '../../stores/navigation-store';
import { useTheme } from '../../hooks/useTheme';
import { DebugConsole } from '../debug/DebugConsole';
import { UpdateBanner } from './UpdateBanner';
import { ArmDisarmButton } from './ArmDisarmButton';
import { ScriptHealthBadge } from '../script-installer/ScriptHealthBadge';
import { QuickLaunchMenu } from './QuickLaunchMenu';
import { betaLabel } from '../../utils/version-label';
import iconImage from '../../assets/icon.png';

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const { connectionState, disconnect } = useConnectionStore();
  const { currentVersion, status, fetchVersion } = useUpdateStore();
  const setView = useNavigationStore((s) => s.setView);

  // Fleet (multi-vehicle/swarm) connects over background transports that don't
  // set the primary connection flag. Surface it as its own status so the pill
  // isn't stuck on "Disconnected" while a live fleet is selected.
  const fleetCount = useActiveVehicleStore((s) => Object.keys(s.knownVehicles).length);
  const activeVehicleKey = useActiveVehicleStore((s) => s.activeVehicleKey);
  const fleetConnected = !connectionState.isConnected && fleetCount > 0;

  useTheme();

  useEffect(() => {
    fetchVersion();
  }, [fetchVersion]);

  // Tick once a second while the link is stale so the banner shows elapsed seconds.
  const [, setNow] = useState(0);
  useEffect(() => {
    if (!connectionState.isStale) return;
    const id = setInterval(() => setNow((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [connectionState.isStale]);

  const staleSeconds = connectionState.isStale && connectionState.staleSince
    ? Math.max(0, Math.floor((Date.now() - connectionState.staleSince) / 1000))
    : 0;

  return (
    <div className="h-screen flex flex-col bg-surface-base">
      {/* Header */}
      <header className="h-14 border-b border-subtle bg-surface-nav backdrop-blur-sm flex items-center shrink-0 relative z-50">
        {/* Logo sits in a nav-rail-width slot so it lines up with the sidebar icons */}
        <div className="w-14 flex items-center justify-center shrink-0">
          <img src={iconImage} alt="ArduDeck" className="h-8 w-8 rounded-md object-cover" />
        </div>
        <h1 className="text-lg font-semibold text-content">ArduDeck</h1>

        <div className="ml-auto flex items-center gap-4 pr-6">
          {/* Version badge */}
          {currentVersion && (
            <button
              onClick={() => setView('settings')}
              className="flex items-center gap-1.5 text-content-tertiary hover:text-content-secondary transition-colors"
              title="About ArduDeck"
            >
              <span className="text-xs">{betaLabel(currentVersion)}</span>
              {(status === 'available' || status === 'downloaded') && (
                <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
              )}
            </button>
          )}

          {/* FC-side Lua script health (only when advanced commands unlocked + AD_HB seen) */}
          <ScriptHealthBadge />

          {/* ARM / DISARM button */}
          <ArmDisarmButton />

          {/* Connection status */}
          {connectionState.isConnected ? (
            <button
              onClick={disconnect}
              title={connectionState.isStale ? `No data for ${staleSeconds}s. Click to disconnect` : 'Click to disconnect'}
              className={`group flex items-center gap-2.5 px-3 py-1.5 rounded-full bg-surface border transition-colors cursor-pointer ${
                connectionState.isStale
                  ? 'border-yellow-500/50 hover:border-red-500/50'
                  : 'border-emerald-500/30 hover:border-red-500/50'
              }`}
            >
              {connectionState.isStale ? (
                <svg className="w-3 h-3 text-yellow-400 animate-pulse" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2L1 21h22L12 2zm0 6l7.53 13H4.47L12 8zm-1 4v4h2v-4h-2zm0 6v2h2v-2h-2z" />
                </svg>
              ) : (
                <div className="status-dot status-dot-connected group-hover:bg-red-400" />
              )}
              <span className={`text-sm font-medium transition-colors ${
                connectionState.isStale ? 'text-yellow-300' : 'text-content-secondary group-hover:text-red-300'
              }`}>
                {connectionState.isStale ? `No data ${staleSeconds}s` : connectionState.transport}
              </span>
              <svg className="w-3 h-3 text-content-tertiary opacity-0 group-hover:opacity-100 group-hover:text-red-400 transition-all" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          ) : fleetConnected ? (
            <button
              onClick={() => setView('telemetry')}
              title="Fleet connected over multi-vehicle links. Click to open telemetry."
              className="group flex items-center gap-2.5 px-3 py-1.5 rounded-full bg-surface border border-emerald-500/30 hover:border-emerald-500/50 transition-colors cursor-pointer"
            >
              <div className="status-dot status-dot-connected" />
              <span className="text-sm font-medium text-content-secondary group-hover:text-content">
                Fleet ({fleetCount}){activeVehicleKey ? '' : ' · none selected'}
              </span>
            </button>
          ) : (
            <div className={`flex items-center gap-2.5 px-3 py-1.5 rounded-full bg-surface border ${
              connectionState.isWaitingForHeartbeat
                ? 'border-yellow-500/30'
                : 'border-subtle'
            }`}>
              {connectionState.isWaitingForHeartbeat ? (
                <svg className="w-2.5 h-2.5 text-yellow-400 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <div className="status-dot status-dot-disconnected" />
              )}
              <span className="text-sm font-medium text-content-secondary">
                {connectionState.isWaitingForHeartbeat ? 'Waiting...' : 'Disconnected'}
              </span>
            </div>
          )}

          {/* Quick Launch: open self-contained tools in their own window. */}
          <QuickLaunchMenu />
        </div>
      </header>

      {/* Update notification banner */}
      <UpdateBanner />

      {/* Main content */}
      <div className="flex-1 overflow-hidden">{children}</div>

      {/* Debug console */}
      <DebugConsole />
    </div>
  );
}
