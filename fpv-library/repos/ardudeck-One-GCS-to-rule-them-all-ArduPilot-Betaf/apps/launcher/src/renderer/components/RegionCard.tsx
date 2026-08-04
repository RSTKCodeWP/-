import { AlertTriangle, HardDrive, Mountain, MapPin, Ruler, Satellite } from 'lucide-react';
import type { RegionSummary } from '../../shared/region.js';
import {
  formatBytes,
  formatElevation,
  formatExtent,
  formatImageryDate,
  formatLatLon,
} from '../lib/format';

interface Props {
  region: RegionSummary;
  selected: boolean;
  onSelect: () => void;
}

function Fact({ icon: Icon, label, value }: { icon: typeof MapPin; label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2 text-xs">
      <Icon size={12} className="shrink-0 translate-y-0.5 text-content-tertiary" />
      <span className="text-content-tertiary">{label}</span>
      <span className="ml-auto tabular-nums text-content-secondary">{value}</span>
    </div>
  );
}

export function RegionCard({ region, selected, onSelect }: Props) {
  const local = region.availability === 'local';
  return (
    <button
      onClick={onSelect}
      className={`card w-full text-left transition-all duration-200 ${
        selected ? 'ring-2 ring-blue-500/70' : 'hover:border-strong'
      }`}
    >
      <div className="card-header flex items-center gap-2">
        <h3 className="text-sm font-semibold">{region.displayName}</h3>
        <span
          className="ml-auto rounded-md px-2 py-0.5 text-xs font-medium"
          style={
            local
              ? { background: 'var(--status-success-bg)', color: 'var(--status-success-fg)' }
              : { background: 'var(--status-info-bg)', color: 'var(--status-info-fg)' }
          }
        >
          {local ? 'Ready to fly' : region.availability}
        </span>
      </div>
      <div className="card-body space-y-1.5">
        <Fact icon={MapPin} label="Home" value={formatLatLon(region.home)} />
        <Fact icon={Mountain} label="Elevation" value={formatElevation(region.elevationM)} />
        <Fact icon={Ruler} label="Ground" value={formatExtent(region.extentM)} />
        <Fact icon={Satellite} label="Imagery" value={formatImageryDate(region.imagery.date)} />
        <Fact icon={HardDrive} label="On disk" value={formatBytes(region.sizeBytes)} />

        {region.warnings.length > 0 && (
          <div
            className="mt-3 space-y-1 rounded-lg p-2 text-xs"
            style={{ background: 'var(--status-warn-bg)', color: 'var(--status-warn-fg)' }}
          >
            {region.warnings.map((w) => (
              <div key={w} className="flex gap-1.5">
                <AlertTriangle size={12} className="shrink-0 translate-y-0.5" />
                <span>{w}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </button>
  );
}
