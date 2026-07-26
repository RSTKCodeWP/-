// Extracts the parameter table embedded in a dataflash log (PARM records).
// ArduPilot writes a full parameter dump at log start, then re-logs any
// parameter that changes during flight - so a name with >1 distinct value is
// an in-flight change worth surfacing loudly. Newer firmwares also log the
// firmware default per parameter, letting us flag user-modified values.

export interface LogParamEntry {
  name: string;
  /** Value at log start (first PARM record). */
  first: number;
  /** Value at log end (last PARM record). */
  last: number;
  /** Firmware default, when the log records it (PARM.Default, 2023+). */
  default?: number;
  /** In-flight transitions AFTER the initial dump: time + new value. */
  changes: { timeS: number; value: number }[];
}

type LogMessages = Record<string, { type: string; timeUs: number; fields: Record<string, number | string> }[]>;

export function extractLogParams(log: { messages: LogMessages }): LogParamEntry[] {
  const byName = new Map<string, LogParamEntry>();

  for (const m of log.messages['PARM'] ?? []) {
    const name = typeof m.fields['Name'] === 'string' ? m.fields['Name'] : '';
    const value = m.fields['Value'];
    if (!name || typeof value !== 'number') continue;
    const def = m.fields['Default'];

    const existing = byName.get(name);
    if (!existing) {
      byName.set(name, {
        name,
        first: value,
        last: value,
        default: typeof def === 'number' && Number.isFinite(def) ? def : undefined,
        changes: [],
      });
    } else {
      if (value !== existing.last) {
        existing.changes.push({ timeS: m.timeUs / 1_000_000, value });
      }
      existing.last = value;
    }
  }

  return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
}

/** Differs-from-default check with a relative epsilon (float32 round-trips). */
export function isNonDefault(p: LogParamEntry): boolean {
  if (p.default === undefined) return false;
  const scale = Math.max(Math.abs(p.default), Math.abs(p.last), 1);
  return Math.abs(p.last - p.default) > scale * 1e-6;
}

/** Compact param value formatting (params are float32; hide the noise). */
export function fmtParamValue(v: number): string {
  if (Number.isInteger(v)) return String(v);
  // Round to float32-meaningful digits, then trim trailing zeros.
  return String(Number(v.toPrecision(7)));
}
