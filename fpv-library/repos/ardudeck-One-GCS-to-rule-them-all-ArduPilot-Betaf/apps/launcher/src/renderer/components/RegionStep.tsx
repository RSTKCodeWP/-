import { FolderOpen, RefreshCw } from 'lucide-react';
import { useLauncherStore } from '../stores/launcher-store';
import { RegionCard } from './RegionCard';

export function RegionStep() {
  const regions = useLauncherStore((s) => s.regions);
  const sourceLabel = useLauncherStore((s) => s.regionSourceLabel);
  const errors = useLauncherStore((s) => s.regionErrors);
  const loading = useLauncherStore((s) => s.regionsLoading);
  const selected = useLauncherStore((s) => s.selectedRegion);
  const selectRegion = useLauncherStore((s) => s.selectRegion);
  const refresh = useLauncherStore((s) => s.refreshRegions);
  const roots = useLauncherStore((s) => s.info?.regionRoots ?? []);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div>
          <h2 className="text-sm font-semibold">Region</h2>
          <p className="text-xs text-content-tertiary">
            {sourceLabel || 'Scanning'}
            {regions.length > 0 ? ` · ${regions.length} available` : ''}
          </p>
        </div>
        <button className="btn btn-secondary ml-auto text-sm" onClick={() => void refresh()}>
          <span className="flex items-center gap-1.5">
            <RefreshCw size={13} className={loading ? 'animate-spin' : undefined} />
            Rescan
          </span>
        </button>
      </div>

      {errors.map((e) => (
        <div
          key={e}
          className="rounded-lg p-3 text-sm"
          style={{ background: 'var(--status-danger-bg)', color: 'var(--status-danger-fg)' }}
        >
          {e}
        </div>
      ))}

      {regions.length === 0 && !loading && errors.length === 0 && (
        <div className="card card-body text-sm text-content-secondary">
          No baked regions found. Run <code>tools/bake_region.sh &lt;region&gt;</code> in the game
          checkout, then rescan.
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {regions.map((region) => (
          <RegionCard
            key={region.name}
            region={region}
            selected={region.name === selected}
            onSelect={() => selectRegion(region.name)}
          />
        ))}
      </div>

      <details className="text-xs text-content-tertiary">
        <summary className="cursor-pointer select-none">Where the launcher looks</summary>
        <ul className="mt-2 space-y-1">
          {roots.map((root) => (
            <li key={root} className="flex items-center gap-1.5 font-mono">
              <FolderOpen size={11} className="shrink-0" />
              {root}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
