import type { VehicleProfile, WingShape, VtolStyle, MotorArrangement } from '../../../stores/settings-store.js';

interface ConfigSelectorsProps {
  vehicle: VehicleProfile;
  onUpdate: (updates: Partial<VehicleProfile>) => void;
}

const WING_SHAPES: Array<{ value: WingShape; label: string; hint: string }> = [
  { value: 'standard',     label: 'Standard',      hint: 'Traditional fuselage with separate elevator/rudder/ailerons' },
  { value: 'delta',        label: 'Delta',         hint: 'Triangular wing, elevons combine pitch+roll' },
  { value: 'flying-wing',  label: 'Flying Wing',   hint: 'No tail, wing-only — elevons for control' },
  { value: 'v-tail',       label: 'V-Tail',        hint: 'Two surfaces mix pitch and yaw' },
  { value: 'biplane',      label: 'Biplane',       hint: 'Two wings stacked — rare, nostalgic' },
  { value: 'inverted-v',   label: 'Inverted V',    hint: 'Inverted-V tail' },
];

const VTOL_STYLES: Array<{ value: VtolStyle; label: string; hint: string }> = [
  { value: 'quadplane',   label: 'Quadplane',    hint: 'Plane + separate vertical lift motors' },
  { value: 'tailsitter',  label: 'Tailsitter',   hint: 'Sits on its tail, tilts to fly forward' },
  { value: 'tiltrotor',   label: 'Tiltrotor',    hint: 'Motors tilt from vertical to horizontal' },
  { value: 'tiltwing',    label: 'Tiltwing',     hint: 'Whole wing tilts with the motors' },
];

const MOTOR_ARRANGEMENTS: Array<{ value: MotorArrangement; label: string; hint: string }> = [
  { value: 'quad-x',       label: 'Quad X',       hint: '4 motors in X pattern' },
  { value: 'quad-plus',    label: 'Quad +',       hint: '4 motors in + pattern' },
  { value: 'quad-h',       label: 'Quad H',       hint: '4 motors in H pattern' },
  { value: 'hex-x',        label: 'Hex X',        hint: '6 motors in X pattern' },
  { value: 'hex-plus',     label: 'Hex +',        hint: '6 motors in + pattern' },
  { value: 'octo-x',       label: 'Octo X',       hint: '8 motors in X pattern' },
  { value: 'octo-plus',    label: 'Octo +',       hint: '8 motors in + pattern' },
  { value: 'y6',           label: 'Y6',           hint: '3 arms, 2 coaxial motors each' },
  { value: 'tri',          label: 'Tricopter',    hint: '3 motors + yaw servo' },
  { value: 'coaxial',      label: 'Coaxial X8',   hint: '4 coaxial pairs stacked' },
  { value: 'inline-2',     label: 'Inline 2',     hint: '2 motors side-by-side' },
  { value: 'twin-tractor', label: 'Twin-Tractor', hint: '2 motors pulling from wing LE' },
  { value: 'twin-pusher',  label: 'Twin-Pusher',  hint: '2 motors pushing from wing TE' },
];

/**
 * The three orthogonal configuration selectors + live param-hint row.
 * Only renders what's relevant for the vehicle type.
 */
export function ConfigSelectors({ vehicle, onUpdate }: ConfigSelectorsProps) {
  const showWing = vehicle.type === 'plane' || vehicle.type === 'vtol';
  const showVtol = vehicle.type === 'vtol';
  const showMotor = vehicle.type === 'copter' || vehicle.type === 'vtol';

  if (!showWing && !showVtol && !showMotor) return null;

  return (
    <div className="grid grid-cols-2 gap-4">
      {showWing && (
        <Selector
          label="Wing Shape"
          value={vehicle.wingShape}
          options={WING_SHAPES}
          onChange={v => onUpdate({ wingShape: v as WingShape })}
        />
      )}
      {showVtol && (
        <Selector
          label="VTOL Style"
          value={vehicle.vtolStyle}
          options={VTOL_STYLES}
          onChange={v => onUpdate({ vtolStyle: v as VtolStyle })}
        />
      )}
      {showMotor && (
        <Selector
          label="Motor Arrangement"
          value={vehicle.motorArrangement}
          options={MOTOR_ARRANGEMENTS}
          onChange={v => onUpdate({ motorArrangement: v as MotorArrangement })}
        />
      )}
    </div>
  );
}

interface SelectorProps<T extends string> {
  label: string;
  value: T | undefined;
  options: Array<{ value: T; label: string; hint: string }>;
  onChange: (value: T) => void;
}

function Selector<T extends string>({ label, value, options, onChange }: SelectorProps<T>) {
  const current = options.find(o => o.value === value);
  return (
    <div>
      <label className="block text-sm font-medium text-content mb-1.5">{label}</label>
      <select
        value={value ?? ''}
        onChange={e => onChange(e.target.value as T)}
        className="w-full px-3 py-2 bg-surface-input border border-border rounded-lg text-content focus:outline-none focus:border-blue-500"
      >
        <option value="">— select —</option>
        {options.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      {current && (
        <div className="text-[10px] text-content-secondary mt-1">{current.hint}</div>
      )}
    </div>
  );
}

