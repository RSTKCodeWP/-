import { useLauncherStore } from '../stores/launcher-store';
import type { GameState } from '../../shared/ipc-channels.js';

const STATE_LABEL: Record<GameState, string> = {
  idle: 'Idle',
  preparing: 'Preparing region',
  starting: 'Starting',
  running: 'Flying',
  exited: 'Game closed',
  failed: 'Game failed',
};

const STATE_COLOR: Record<GameState, string> = {
  idle: 'var(--text-tertiary)',
  preparing: 'var(--status-info)',
  starting: 'var(--status-info)',
  running: 'var(--status-success)',
  exited: 'var(--text-tertiary)',
  failed: 'var(--status-danger)',
};

export function TopBar() {
  const info = useLauncherStore((s) => s.info);
  const status = useLauncherStore((s) => s.gameStatus);

  return (
    // Padded left on macOS so the title clears the inset traffic lights.
    <header className="flex h-14 shrink-0 items-center gap-3 border-b px-4 pl-20">
      <div className="min-w-0">
        <h1 className="text-sm font-semibold leading-tight">ArduDeck Trainer</h1>
        <p className="truncate text-xs text-content-tertiary">
          {info?.game ? info.game.label : 'No game found'}
          {info ? ` · launcher ${info.appVersion}` : ''}
        </p>
      </div>

      <div className="ml-auto flex items-center gap-2 text-xs text-content-secondary">
        <span className="status-dot" style={{ background: STATE_COLOR[status.state] }} />
        {STATE_LABEL[status.state]}
        {status.pid !== null && <span className="text-content-tertiary">pid {status.pid}</span>}
        {status.error && <span style={{ color: 'var(--status-danger-fg)' }}>{status.error}</span>}
      </div>
    </header>
  );
}
