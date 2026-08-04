import { Construction } from 'lucide-react';

interface Props {
  title: string;
  summary: string;
  items: string[];
}

/**
 * A step that exists in the flow but does nothing yet. Visible on purpose: the shape of the
 * flow is part of what Phase 1 is proving, and a step that is silently absent reads as a bug.
 */
export function PlaceholderStep({ title, summary, items }: Props) {
  return (
    <div className="card max-w-2xl">
      <div className="card-header flex items-center gap-2">
        <Construction size={16} style={{ color: 'var(--status-warn)' }} />
        <h2 className="text-sm font-semibold">{title}</h2>
        <span
          className="ml-auto rounded-md px-2 py-0.5 text-xs font-medium"
          style={{ background: 'var(--status-warn-bg)', color: 'var(--status-warn-fg)' }}
        >
          Not wired up yet
        </span>
      </div>
      <div className="card-body space-y-3">
        <p className="text-sm text-content-secondary">{summary}</p>
        <ul className="space-y-1.5 text-sm text-content-tertiary">
          {items.map((item) => (
            <li key={item} className="flex gap-2">
              <span aria-hidden className="select-none">
                &bull;
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
        <p className="text-xs text-content-tertiary">
          Nothing here is written to the launch config. The game keeps its own defaults and its
          in-game keys until this step is real.
        </p>
      </div>
    </div>
  );
}
