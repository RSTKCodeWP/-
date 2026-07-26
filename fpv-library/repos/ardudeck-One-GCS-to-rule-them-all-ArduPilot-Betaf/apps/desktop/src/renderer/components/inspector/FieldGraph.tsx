/**
 * FieldGraph — single-field time-series plot, intended to be opened in a
 * detached window from the MAVLink Inspector. Each instance plots exactly one
 * (sysid, compid, msgid, fieldName) tuple. Keeps a rolling window of the most
 * recent samples and renders an SVG line — light, dependency-free, and fine
 * for any update rate the FC produces. Theme-aware: line/fill use accent
 * colors that hold up in both light and dark.
 */

import { useEffect, useState } from 'react';
import {
  appendSample,
  getFieldValue,
  getMessageStats,
  getSamples,
  panelIdForGraph,
  useInspectorStore,
  type GraphSample,
} from '../../stores/inspector-store';

interface FieldGraphProps {
  sysid: number;
  compid: number;
  msgid: number;
  messageName: string;
  fieldName: string;
  /** Optional override for how many points of history to keep. Default 600. */
  historyPoints?: number;
}

export function FieldGraph(propsIn: Record<string, unknown>): JSX.Element {
  const props = propsIn as unknown as FieldGraphProps;
  const sysid = Number(props.sysid);
  const compid = Number(props.compid);
  const msgid = Number(props.msgid);
  const messageName = String(props.messageName ?? `MSG_${msgid}`);
  const fieldName = String(props.fieldName ?? '');

  // Samples live at the module level (sampleBuffers in inspector-store) so
  // they survive component unmounts — view switches AND popout seeding both
  // work without losing history. We trigger React re-renders with a version
  // counter rather than reading the array via state.
  const panelId = panelIdForGraph({
    sysid, compid, msgid, messageName, fieldName,
  });
  const [, setVersion] = useState(0);

  const tick = useInspectorStore((s) => s.tick);
  useEffect(() => {
    const stats = getMessageStats(sysid, compid, msgid);
    if (!stats) return;
    // Skip the tick if the underlying message hasn't advanced since the last
    // sample we pushed. Compare against the most recent sample's timestamp
    // (which lives in the shared buffer, so it's authoritative across re-
    // mounts and seedings). This is what makes Pause freeze the graph and
    // also handles a message that simply stops arriving.
    const existing = getSamples(panelId);
    const lastT = existing.length > 0 ? existing[existing.length - 1]!.t : 0;
    if (stats.lastRxtime <= lastT) return;
    const v = getFieldValue(sysid, compid, msgid, fieldName);
    if (v === null) return;
    appendSample(panelId, stats.lastRxtime, v);
    setVersion((x) => x + 1);
  }, [tick, sysid, compid, msgid, fieldName, panelId]);

  const samples: GraphSample[] = getSamples(panelId);
  const latest = samples.length > 0 ? samples[samples.length - 1]!.v : null;
  // Not memoized: the samples array is mutated in place (its identity is
  // stable across pushes), so a useMemo keyed on it would never recompute.
  // 600 samples × 3 reductions is well under a millisecond.
  const stats = computeStats(samples);

  const handleClear = () => {
    // Wipe just this graph's buffer (not every graph's). Mutating the array
    // in place is fine — sampleBuffers stores the same reference.
    const list = getSamples(panelId);
    list.length = 0;
    setVersion((x) => x + 1);
  };

  return (
    <div className="h-full flex flex-col bg-surface-base text-content">
      {/* Header */}
      <div className="px-4 py-3 border-b border-subtle bg-surface-nav flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/30 flex items-center justify-center flex-shrink-0">
          <svg className="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M7 12l3-3 3 3 4-4M5 21h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v14a2 2 0 002 2z" />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-mono text-sm font-medium text-content truncate">
            {messageName}<span className="text-content-tertiary">.</span>{fieldName}
          </div>
          <div className="text-xs text-content-secondary tabular-nums">
            sysid {sysid} · compid {compid} · msgid {msgid}
          </div>
        </div>
        <button
          onClick={handleClear}
          className="px-2.5 py-1.5 text-xs rounded-md bg-surface border border-subtle text-content-secondary hover:bg-surface-raised hover:text-content transition-colors"
        >
          Clear
        </button>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-5 gap-px bg-surface-inset/40 border-b border-subtle">
        <Stat label="Current" value={latest !== null ? formatNumber(latest) : '—'} accent="text-blue-400" />
        <Stat label="Min" value={stats.min !== null ? formatNumber(stats.min) : '—'} />
        <Stat label="Max" value={stats.max !== null ? formatNumber(stats.max) : '—'} />
        <Stat label="Avg" value={stats.avg !== null ? formatNumber(stats.avg) : '—'} />
        <Stat label="Samples" value={samples.length.toString()} />
      </div>

      {/* Plot */}
      <div className="flex-1 min-h-0 p-3">
        <GraphSvg samples={samples} />
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  accent = 'text-content',
}: {
  label: string;
  value: string;
  accent?: string;
}): JSX.Element {
  return (
    <div className="bg-surface px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-content-tertiary">{label}</div>
      <div className={`text-sm font-mono tabular-nums ${accent}`}>{value}</div>
    </div>
  );
}

function GraphSvg({ samples }: { samples: GraphSample[] }): JSX.Element {
  if (samples.length < 2) {
    return (
      <div className="h-full w-full flex items-center justify-center text-content-secondary text-sm border border-dashed border-subtle rounded-lg">
        Waiting for samples…
      </div>
    );
  }

  const stats = computeStats(samples);
  const min = stats.min ?? 0;
  const max = stats.max ?? 1;
  const range = max - min || 1;
  const padded = range * 0.1;
  const yMin = min - padded;
  const yMax = max + padded;
  const tMin = samples[0]!.t;
  const tMax = samples[samples.length - 1]!.t;
  const tRange = tMax - tMin || 1;

  const W = 1000;
  const H = 400;

  const path = samples.map((s, i) => {
    const x = ((s.t - tMin) / tRange) * W;
    const y = H - ((s.v - yMin) / (yMax - yMin)) * H;
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(' ');

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((p) => {
    const y = p * H;
    const val = yMax - p * (yMax - yMin);
    return { y, val };
  });

  // Use currentColor so the grid/labels follow the theme; the wrapping
  // <g> sets `color: text-content-tertiary` via a CSS variable.
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full text-content-tertiary" preserveAspectRatio="none">
      <defs>
        <linearGradient id="fg-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="rgb(96, 165, 250)" stopOpacity="0.3" />
          <stop offset="100%" stopColor="rgb(96, 165, 250)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {gridLines.map(({ y, val }, i) => (
        <g key={i}>
          <line
            x1={0} x2={W} y1={y} y2={y}
            stroke="currentColor" strokeOpacity="0.35" strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
          <text
            x={4} y={y - 4}
            fill="currentColor" fontSize="14" fontFamily="monospace"
          >
            {formatNumber(val)}
          </text>
        </g>
      ))}
      <path d={`${path} L${W} ${H} L0 ${H} Z`} fill="url(#fg-fill)" />
      <path
        d={path}
        fill="none" stroke="rgb(96, 165, 250)" strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

function computeStats(samples: GraphSample[]): {
  min: number | null;
  max: number | null;
  avg: number | null;
} {
  if (samples.length === 0) return { min: null, max: null, avg: null };
  let min = samples[0]!.v;
  let max = samples[0]!.v;
  let sum = 0;
  for (const s of samples) {
    if (s.v < min) min = s.v;
    if (s.v > max) max = s.v;
    sum += s.v;
  }
  return { min, max, avg: sum / samples.length };
}

function formatNumber(v: number): string {
  if (Number.isInteger(v)) return v.toString();
  if (Math.abs(v) >= 1000) return v.toFixed(0);
  if (Math.abs(v) >= 1) return v.toFixed(3);
  return v.toFixed(5);
}
