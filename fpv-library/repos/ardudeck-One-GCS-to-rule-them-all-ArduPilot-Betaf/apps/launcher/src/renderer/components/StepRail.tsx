import { Globe2, CloudSun, Plane, Check } from 'lucide-react';
import type { StepId } from '../stores/launcher-store';

interface StepDef {
  id: StepId;
  label: string;
  hint: string;
  icon: typeof Globe2;
  ready: boolean;
}

const STEPS: StepDef[] = [
  { id: 'region', label: 'Region', hint: 'Where you fly', icon: Globe2, ready: true },
  { id: 'conditions', label: 'Conditions', hint: 'Time and weather', icon: CloudSun, ready: false },
  { id: 'vehicle', label: 'Vehicle', hint: 'Firmware and frame', icon: Plane, ready: false },
];

interface Props {
  step: StepId;
  onStep: (step: StepId) => void;
  regionChosen: boolean;
}

export function StepRail({ step, onStep, regionChosen }: Props) {
  return (
    <nav className="w-56 shrink-0 flex flex-col gap-1 p-3">
      {STEPS.map((s, index) => {
        const active = s.id === step;
        const done = s.id === 'region' && regionChosen;
        const Icon = s.icon;
        return (
          <button
            key={s.id}
            onClick={() => onStep(s.id)}
            className={`flex items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-all duration-200 ${
              active ? 'bg-surface-raised' : 'hover:bg-surface'
            }`}
          >
            <span
              className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-xs font-semibold ${
                active ? 'bg-blue-500 text-white' : 'bg-surface-inset text-content-secondary'
              }`}
            >
              {done && !active ? <Check size={13} /> : index + 1}
            </span>
            <span className="min-w-0">
              <span className="flex items-center gap-1.5 text-sm font-medium">
                <Icon size={14} className="opacity-70" />
                {s.label}
              </span>
              <span className="block text-xs text-content-tertiary">
                {s.ready ? s.hint : 'Not wired up yet'}
              </span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}
