import { useEffect, useRef } from 'react';
import { useLauncherStore } from '../stores/launcher-store';

/**
 * The game's stdout, verbatim. It is the fastest way to see whether the config was read and
 * which region actually loaded, and the launcher is the game's parent anyway so the pipe is
 * already there.
 */
export function GameLogPanel() {
  const lines = useLauncherStore((s) => s.gameLog);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [lines.length]);

  if (lines.length === 0) return null;

  return (
    <details className="card mt-4" open>
      <summary className="card-header cursor-pointer select-none text-sm font-semibold">
        Game output
      </summary>
      <div className="max-h-56 overflow-y-auto p-3 font-mono text-xs leading-relaxed">
        {lines.map((line, index) => (
          <div
            key={index}
            style={line.stream === 'stderr' ? { color: 'var(--status-danger-fg)' } : undefined}
            className="whitespace-pre-wrap break-all text-content-secondary"
          >
            {line.line}
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </details>
  );
}
