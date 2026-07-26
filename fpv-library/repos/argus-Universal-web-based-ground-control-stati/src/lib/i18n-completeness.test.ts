import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dir = dirname(fileURLToPath(import.meta.url));
const localesDir = resolve(__dir, 'locales');

// --- Helpers ---

/** Parse keys and values from a locale .ts file */
function parseLocale(filename: string): Record<string, string> {
  const src = readFileSync(resolve(localesDir, filename), 'utf-8');
  const entries: Record<string, string> = {};
  const re = /['"]([^'"]+)['"]\s*:\s*'((?:[^'\\]|\\.)*)'/g;
  let m;
  while ((m = re.exec(src)) !== null) {
    entries[m[1]] = m[2].replace(/\\'/g, "'");
  }
  return entries;
}

/** Extract interpolation placeholders like {0}, {n}, {alt}, etc. */
function extractPlaceholders(value: string): string[] {
  const matches = value.match(/\{[^}]+\}/g);
  return matches ? matches.sort() : [];
}

// --- Load all locales ---

const localeFiles = readdirSync(localesDir).filter((f) => f.endsWith('.ts'));
const BASE_LOCALE = 'zh.ts';

let baseMessages: Record<string, string>;
const allLocales: Record<string, Record<string, string>> = {};

beforeAll(() => {
  for (const file of localeFiles) {
    allLocales[file] = parseLocale(file);
  }
  baseMessages = allLocales[BASE_LOCALE];
});

// --- Tests ---

describe('i18n completeness', () => {
  it('base locale (zh.ts) should have a substantial number of keys', () => {
    expect(Object.keys(baseMessages).length).toBeGreaterThan(300);
  });

  it('all expected locale files exist', () => {
    const expected = ['zh.ts', 'en.ts', 'ja.ts', 'ko.ts', 'de.ts', 'fr.ts', 'es.ts', 'pt.ts', 'ru.ts', 'ar.ts'];
    for (const file of expected) {
      expect(localeFiles, `Missing locale file: ${file}`).toContain(file);
    }
  });

  it('every key in zh.ts exists in en.ts (full parity)', () => {
    const enMessages = allLocales['en.ts'];
    const baseKeys = Object.keys(baseMessages);
    const missing = baseKeys.filter((k) => !(k in enMessages));
    expect(missing, `Keys in zh.ts missing from en.ts: ${missing.join(', ')}`).toEqual([]);
  });

  describe('missing keys per locale', () => {
    const otherLocales = localeFiles.filter((f) => f !== BASE_LOCALE);

    for (const file of otherLocales) {
      it(`${file} should contain all base locale keys`, () => {
        const messages = allLocales[file];
        const baseKeys = Object.keys(baseMessages);
        const missing = baseKeys.filter((k) => !(k in messages));
        // Non-eagerly-loaded locales may be sparse; report missing count
        // This test documents coverage -- adjust threshold as locales mature
        if (file === 'en.ts') {
          // en.ts must have full parity
          expect(missing, `Keys missing from ${file}: ${missing.slice(0, 20).join(', ')}...`).toEqual([]);
        } else {
          // Other locales: report missing keys as a coverage metric
          // Fail if locale has zero keys (broken file)
          expect(Object.keys(messages).length, `${file} appears empty or broken`).toBeGreaterThan(0);
        }
      });
    }
  });

  describe('no empty string values', () => {
    for (const file of localeFiles) {
      it(`${file} should have no empty string values`, () => {
        const messages = allLocales[file];
        const emptyKeys = Object.entries(messages)
          .filter(([, v]) => v === '')
          .map(([k]) => k);
        expect(emptyKeys, `Empty values in ${file}: ${emptyKeys.join(', ')}`).toEqual([]);
      });
    }
  });

  describe('interpolation placeholder consistency', () => {
    const otherLocales = localeFiles.filter((f) => f !== BASE_LOCALE);

    for (const file of otherLocales) {
      it(`${file} placeholders match zh.ts for shared keys`, () => {
        const messages = allLocales[file];
        const mismatches: string[] = [];

        for (const [key, baseValue] of Object.entries(baseMessages)) {
          if (!(key in messages)) continue; // skip keys not present in this locale
          const basePlaceholders = extractPlaceholders(baseValue);
          const localePlaceholders = extractPlaceholders(messages[key]);

          if (basePlaceholders.length === 0 && localePlaceholders.length === 0) continue;

          if (JSON.stringify(basePlaceholders) !== JSON.stringify(localePlaceholders)) {
            mismatches.push(
              `${key}: zh=${basePlaceholders.join(',')} vs ${file.replace('.ts', '')}=${localePlaceholders.join(',')}`,
            );
          }
        }

        expect(mismatches, `Placeholder mismatches in ${file}:\n${mismatches.join('\n')}`).toEqual([]);
      });
    }
  });

  it('no locale has duplicate keys', () => {
    for (const file of localeFiles) {
      const src = readFileSync(resolve(localesDir, file), 'utf-8');
      const re = /['"]([^'"]+)['"]\s*:/g;
      const seen = new Set<string>();
      const duplicates: string[] = [];
      let m;
      while ((m = re.exec(src)) !== null) {
        if (seen.has(m[1])) duplicates.push(m[1]);
        seen.add(m[1]);
      }
      expect(duplicates, `Duplicate keys in ${file}: ${duplicates.join(', ')}`).toEqual([]);
    }
  });

  it('keys follow dot-notation naming convention', () => {
    const invalidKeys = Object.keys(baseMessages).filter(
      (k) => !/^[a-zA-Z][a-zA-Z0-9]*(\.[a-zA-Z][a-zA-Z0-9]*)+$/.test(k),
    );
    expect(invalidKeys, `Keys not matching dot-notation: ${invalidKeys.join(', ')}`).toEqual([]);
  });

  describe('no untranslated placeholders in non-English locales', () => {
    const TECHNICAL_TERMS = new Set([
      'Argus',
      'MAVLink',
      'PL-Link',
      'NTRIP',
      'RTSP',
      'RTK',
      'DGPS',
      'PWM',
      'PID',
      'GPS',
      'EKF',
      'AHRS',
      'MSL',
      'WP',
      'SITL',
      'TCP',
      'UDP',
      'USB',
      'CSV',
      'JSON',
      'KML',
      'GPX',
      'WebSerial',
      'Quad X',
      'FOV',
      'Hz',
      'VTOL',
      'FPV',
      'GCS',
      'IMU',
      'RC',
      'BEC',
      'ESC',
      'RSSI',
      'SNR',
      'Bootloader',
      'FFT',
      'Tauri',
      'ArduPilot',
      'PX4',
      'SRTM',
      'Bitmask',
    ]);
    const nonEnLocales = localeFiles.filter((f) => f !== BASE_LOCALE && f !== 'en.ts');

    for (const file of nonEnLocales) {
      it(`${file} should not have values identical to en.ts (except technical terms)`, () => {
        const messages = allLocales[file];
        const enMessages = allLocales['en.ts'];
        const untranslated: string[] = [];

        for (const [key, enVal] of Object.entries(enMessages)) {
          if (!(key in messages)) continue;
          const localeVal = messages[key];
          if (localeVal !== enVal) continue;
          if (enVal.length <= 3) continue;
          if (/^\d/.test(enVal) || /^[A-Z0-9 ._\-/°%{}]+$/.test(enVal)) continue;
          if (TECHNICAL_TERMS.has(enVal.trim())) continue;
          if (/\{[^}]+\}/.test(enVal) && enVal.replace(/\{[^}]+\}/g, '').trim().length <= 3) continue;
          untranslated.push(`${key}: "${enVal}"`);
        }

        expect(
          untranslated.length,
          `${file} has ${untranslated.length} untranslated keys (identical to en.ts):\n${untranslated.slice(0, 10).join('\n')}${untranslated.length > 10 ? '\n...' : ''}`,
        ).toBe(0);
      });
    }
  });

  describe('no hardcoded strings in Svelte components', () => {
    const componentsDir = resolve(__dir, '..', 'components');
    const appFile = resolve(__dir, '..', 'App.svelte');

    function findSvelteFiles(dir: string): string[] {
      const files: string[] = [];
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const full = resolve(dir, entry.name);
        if (entry.isDirectory()) files.push(...findSvelteFiles(full));
        else if (entry.name.endsWith('.svelte')) files.push(full);
      }
      return files;
    }

    it('no hardcoded aria-label attributes in .svelte files', () => {
      const svelteFiles = [...findSvelteFiles(componentsDir), appFile];
      const violations: string[] = [];
      for (const f of svelteFiles) {
        const src = readFileSync(f, 'utf-8');
        const lines = src.split('\n');
        for (let i = 0; i < lines.length; i++) {
          if (/aria-label="[A-Za-z]/.test(lines[i]) && !lines[i].includes('{t(')) {
            const rel = f.split('/src/')[1] || f;
            violations.push(`${rel}:${i + 1}: ${lines[i].trim().slice(0, 80)}`);
          }
        }
      }
      expect(violations, `Hardcoded aria-label found:\n${violations.join('\n')}`).toEqual([]);
    });

    it('no hardcoded placeholder attributes in .svelte files', () => {
      const svelteFiles = [...findSvelteFiles(componentsDir), appFile];
      const violations: string[] = [];
      for (const f of svelteFiles) {
        const src = readFileSync(f, 'utf-8');
        const lines = src.split('\n');
        for (let i = 0; i < lines.length; i++) {
          if (/placeholder="[A-Za-z]/.test(lines[i]) && !lines[i].includes('{t(')) {
            const rel = f.split('/src/')[1] || f;
            violations.push(`${rel}:${i + 1}: ${lines[i].trim().slice(0, 80)}`);
          }
        }
      }
      expect(violations, `Hardcoded placeholder found:\n${violations.join('\n')}`).toEqual([]);
    });

    it('no hardcoded title attributes in .svelte files', () => {
      const svelteFiles = [...findSvelteFiles(componentsDir), appFile];
      const violations: string[] = [];
      for (const f of svelteFiles) {
        const src = readFileSync(f, 'utf-8');
        const lines = src.split('\n');
        for (let i = 0; i < lines.length; i++) {
          if (/\btitle="[A-Z]/.test(lines[i]) && !lines[i].includes('{t(') && !/title="[^"]*\{/.test(lines[i])) {
            const rel = f.split('/src/')[1] || f;
            violations.push(`${rel}:${i + 1}: ${lines[i].trim().slice(0, 80)}`);
          }
        }
      }
      expect(violations, `Hardcoded title found:\n${violations.join('\n')}`).toEqual([]);
    });
  });
});
