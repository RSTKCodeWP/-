export type UnitSystem = 'metric' | 'imperial';

let _system: UnitSystem = 'metric';

export function setUnitSystem(s: UnitSystem) {
  _system = s;
  try {
    localStorage.setItem('argus_units', s);
  } catch {}
}

export function getUnitSystem(): UnitSystem {
  return _system;
}

export function loadUnitSystem() {
  try {
    const saved = localStorage.getItem('argus_units');
    if (saved === 'imperial') _system = 'imperial';
  } catch {}
}

export function altUnit(): string {
  return _system === 'imperial' ? 'ft' : 'm';
}
export function speedUnit(): string {
  return _system === 'imperial' ? 'mph' : 'm/s';
}
export function distUnit(): string {
  return _system === 'imperial' ? 'mi' : 'km';
}
export function vsUnit(): string {
  return _system === 'imperial' ? 'ft/min' : 'm/s';
}

export function fmtAlt(m: number): string {
  if (_system === 'imperial') return (m * 3.28084).toFixed(0);
  return m.toFixed(1);
}

export function fmtSpeed(ms: number): string {
  if (_system === 'imperial') return (ms * 2.23694).toFixed(1);
  return ms.toFixed(1);
}

export function fmtDist(m: number): string {
  if (_system === 'imperial') {
    const mi = m / 1609.344;
    return mi < 0.1 ? (m * 3.28084).toFixed(0) + ' ft' : mi.toFixed(2) + ' mi';
  }
  return m < 1000 ? m.toFixed(0) + ' m' : (m / 1000).toFixed(1) + ' km';
}

export function fmtVs(ms: number): string {
  if (_system === 'imperial') return (ms * 196.85).toFixed(0);
  return ms.toFixed(1);
}
