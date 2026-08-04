import { Play, Square, FileJson } from 'lucide-react';
import { MAX_FPV_UPTILT_DEG } from '../../shared/launch-config.js';
import { useLauncherStore } from '../stores/launcher-store';
import { formatLatLon } from '../lib/format';

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline gap-2 text-xs">
      <span className="text-content-tertiary">{label}</span>
      <span className={`ml-auto truncate text-right text-content-secondary ${mono ? 'font-mono' : ''}`}>
        {value}
      </span>
    </div>
  );
}

export function SummaryPanel() {
  const info = useLauncherStore((s) => s.info);
  const regions = useLauncherStore((s) => s.regions);
  const selectedName = useLauncherStore((s) => s.selectedRegion);
  const uptilt = useLauncherStore((s) => s.fpvUptiltDeg);
  const setUptilt = useLauncherStore((s) => s.setUptilt);
  const launch = useLauncherStore((s) => s.launch);
  const stop = useLauncherStore((s) => s.stop);
  const status = useLauncherStore((s) => s.gameStatus);
  const launchError = useLauncherStore((s) => s.launchError);

  const region = regions.find((r) => r.name === selectedName) ?? null;
  const running = status.state === 'running' || status.state === 'starting';
  const canStart = Boolean(region) && Boolean(info?.game) && !running;

  return (
    <aside className="flex w-80 shrink-0 flex-col gap-3 border-l p-4">
      <div>
        <h2 className="text-sm font-semibold">Launch</h2>
        <p className="text-xs text-content-tertiary">
          What gets written to the config the game boots from.
        </p>
      </div>

      <div className="card card-body space-y-1.5">
        <Row label="Region" value={region?.displayName ?? 'none selected'} />
        <Row label="Home" value={formatLatLon(region?.home ?? null)} />
        <Row label="FPV uptilt" value={`${uptilt} deg`} />
        <Row label="Vehicle" value="game default" />
        <Row label="Conditions" value="game default" />
      </div>

      <div className="card card-body space-y-2">
        <label className="label mb-0 flex items-baseline gap-2" htmlFor="uptilt">
          FPV camera uptilt
          <span className="ml-auto tabular-nums text-content-secondary">{uptilt} deg</span>
        </label>
        <input
          id="uptilt"
          type="range"
          min={0}
          max={MAX_FPV_UPTILT_DEG}
          step={1}
          value={uptilt}
          onChange={(e) => setUptilt(Number(e.target.value))}
          className="w-full accent-blue-500"
        />
        <p className="text-xs text-content-tertiary">
          Every real FPV build angles the camera up, so the horizon stays in frame when the
          aircraft pitches forward. Racers run 35 to 45 deg.
        </p>
      </div>

      {launchError && (
        <div
          className="rounded-lg p-2.5 text-xs"
          style={{ background: 'var(--status-danger-bg)', color: 'var(--status-danger-fg)' }}
        >
          {launchError}
        </div>
      )}

      {info?.gameError && (
        <div
          className="rounded-lg p-2.5 text-xs"
          style={{ background: 'var(--status-warn-bg)', color: 'var(--status-warn-fg)' }}
        >
          {info.gameError}
        </div>
      )}

      <div className="mt-auto space-y-2">
        {info?.configPath && (
          <button
            className="flex w-full items-center gap-1.5 truncate text-left text-xs text-content-tertiary hover:text-content-secondary"
            onClick={() => void window.launcher.openPath(info.configPath)}
            title={info.configPath}
          >
            <FileJson size={11} className="shrink-0" />
            <span className="truncate font-mono">{info.configPath}</span>
          </button>
        )}

        {running ? (
          <button className="btn btn-danger w-full" onClick={() => void stop()}>
            <span className="flex items-center justify-center gap-2">
              <Square size={14} />
              Stop
            </span>
          </button>
        ) : (
          <button className="btn btn-primary w-full" disabled={!canStart} onClick={() => void launch()}>
            <span className="flex items-center justify-center gap-2">
              <Play size={14} />
              Start
            </span>
          </button>
        )}
      </div>
    </aside>
  );
}
