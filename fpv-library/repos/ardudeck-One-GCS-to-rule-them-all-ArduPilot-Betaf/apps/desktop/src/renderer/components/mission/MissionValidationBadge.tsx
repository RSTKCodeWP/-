/**
 * Compact pre-flight validation strip for the waypoint panel. Shows a green
 * "all clear" or an expandable list of errors/warnings from validateMission.
 */
import { useState } from 'react';
import { AlertTriangle, AlertCircle, CheckCircle2, ChevronRight } from 'lucide-react';
import type { ValidationResult } from '../../../shared/mission-validation';

export function MissionValidationBadge({ result }: { result: ValidationResult }) {
  const [open, setOpen] = useState(false);
  const { checks, errorCount, warnCount } = result;

  if (checks.length === 0) {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 text-[11px] text-emerald-300">
        <CheckCircle2 className="w-3.5 h-3.5" />
        Pre-flight OK
      </div>
    );
  }

  const tone = errorCount > 0 ? 'text-red-300' : 'text-amber-300';

  return (
    <div className="px-2 py-1">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1.5 text-[11px] ${tone} hover:brightness-110 w-full`}
      >
        <ChevronRight className={`w-3 h-3 transition-transform ${open ? 'rotate-90' : ''}`} />
        {errorCount > 0 ? <AlertCircle className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
        <span>
          {errorCount > 0 && `${errorCount} error${errorCount === 1 ? '' : 's'}`}
          {errorCount > 0 && warnCount > 0 && ' · '}
          {warnCount > 0 && `${warnCount} warning${warnCount === 1 ? '' : 's'}`}
        </span>
      </button>
      {open && (
        <ul className="mt-1 ml-4 space-y-0.5">
          {checks.map((c) => (
            <li
              key={c.id}
              className={`flex items-start gap-1.5 text-[10px] ${c.severity === 'error' ? 'text-red-300' : 'text-amber-300'}`}
            >
              {c.severity === 'error' ? (
                <AlertCircle className="w-3 h-3 mt-px shrink-0" />
              ) : (
                <AlertTriangle className="w-3 h-3 mt-px shrink-0" />
              )}
              <span className="text-content-secondary">{c.message}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
