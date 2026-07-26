import { describe, it, expect, vi, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dir = dirname(fileURLToPath(import.meta.url));

function extractKeys(file: string): Set<string> {
  const src = readFileSync(resolve(__dir, file), 'utf-8');
  const keys = new Set<string>();
  const re = /^\s+'([^']+)':/gm;
  let m;
  while ((m = re.exec(src)) !== null) keys.add(m[1]);
  return keys;
}

const zhKeys = extractKeys('locales/zh.ts');
const enKeys = extractKeys('locales/en.ts');

describe('i18n key parity', () => {
  it('every ZH key has an EN key', () => {
    const missing = [...zhKeys].filter((k) => !enKeys.has(k));
    expect(missing, `ZH keys missing from EN: ${missing.join(', ')}`).toEqual([]);
  });

  it('every EN key has a ZH key', () => {
    const extra = [...enKeys].filter((k) => !zhKeys.has(k));
    expect(extra, `EN keys missing from ZH: ${extra.join(', ')}`).toEqual([]);
  });

  it('has at least 300 keys', () => {
    expect(zhKeys.size).toBeGreaterThan(300);
    expect(enKeys.size).toBeGreaterThan(300);
  });
});

// --- Functional tests for i18n module ---
// These test the runtime behavior of i18n functions.

// Mock the lazy locale loaders before importing the module
vi.mock('./locales/ja', () => ({ default: { 'app.name': 'Argus-JA', item: 'アイテム {n}' } }));
vi.mock('./locales/ko', () => ({ default: { 'app.name': 'Argus-KO' } }));
vi.mock('./locales/de', () => ({ default: { 'app.name': 'Argus-DE' } }));

// Stub localStorage before import
const localStorageMock = {
  _store: {} as Record<string, string>,
  getItem: vi.fn((key: string) => localStorageMock._store[key] ?? null),
  setItem: vi.fn((key: string, val: string) => {
    localStorageMock._store[key] = val;
  }),
  removeItem: vi.fn((key: string) => {
    delete localStorageMock._store[key];
  }),
  clear: vi.fn(() => {
    localStorageMock._store = {};
  }),
};
vi.stubGlobal('localStorage', localStorageMock);

const {
  i18nState,
  t,
  setLocale,
  getLocale,
  onLocaleChange,
  tp,
  fmtDate,
  fmtTime,
  fmtNumber,
  loadLocale,
  VALID_LOCALES,
  LOCALE_BETA,
} = await import('./i18n.svelte');

describe('i18n runtime', () => {
  beforeEach(() => {
    i18nState.locale = 'zh';
    localStorageMock._store = {};
    localStorageMock.getItem.mockClear();
    localStorageMock.setItem.mockClear();
  });

  describe('t()', () => {
    it('returns ZH translation for known key when locale is zh', () => {
      i18nState.locale = 'zh';
      expect(t('app.name')).toBe('Argus');
    });

    it('returns the key itself if not found in any dict', () => {
      expect(t('nonexistent.key.xyz')).toBe('nonexistent.key.xyz');
    });
  });

  describe('getLocale()', () => {
    it('returns current locale', () => {
      i18nState.locale = 'en';
      expect(getLocale()).toBe('en');
    });
  });

  describe('setLocale()', () => {
    it('sets locale to en (pre-loaded)', () => {
      setLocale('en');
      expect(i18nState.locale).toBe('en');
      expect(localStorageMock.setItem).toHaveBeenCalledWith('argus_locale', 'en');
    });

    it('lazy-loads a non-primary locale (ja)', async () => {
      setLocale('ja');
      expect(i18nState.locale).toBe('ja');
      expect(localStorageMock.setItem).toHaveBeenCalledWith('argus_locale', 'ja');
      // Give the async loader time to resolve
      await vi.waitFor(() => {
        expect(t('app.name')).toBe('Argus-JA');
      });
    });

    it('calls the onLocaleChange callback', () => {
      const cb = vi.fn();
      onLocaleChange(cb);
      setLocale('en');
      expect(cb).toHaveBeenCalledWith('en');
      // Clean up
      onLocaleChange(null as any);
    });
  });

  describe('onLocaleChange()', () => {
    it('registers a callback that fires on setLocale', () => {
      const cb = vi.fn();
      onLocaleChange(cb);
      setLocale('zh');
      expect(cb).toHaveBeenCalledWith('zh');
      setLocale('en');
      expect(cb).toHaveBeenCalledWith('en');
      onLocaleChange(null as any);
    });
  });

  describe('tp() plural function', () => {
    it('replaces {n} with count in zh (no plural suffix)', () => {
      i18nState.locale = 'zh';
      // Use a known key that contains {n} or fallback to the key itself
      const result = tp('nonexistent', 3);
      // Since key not found, returns "nonexistent" with no {n} to replace
      expect(result).toBe('nonexistent');
    });

    it('adds s suffix for EN when count != 1 and word does not end in s/x/z', () => {
      i18nState.locale = 'en';
      // t('item_label') will return the key itself since it may not exist
      // Use a key that returns something ending in a normal word
      // We'll mock a key that translates to a string ending with a word
      const result = tp('app.name', 2); // "Argus" -> count=2 -> "Arguss"?
      // Actually 'Argus' ends with 's', so it should get 'es' suffix
      expect(result).toBe('Arguses');
    });

    it('adds es suffix for EN words ending with s', () => {
      i18nState.locale = 'en';
      // 'app.name' translates to 'Argus' in EN - ends with 's'
      const result = tp('app.name', 5);
      expect(result).toBe('Arguses');
    });

    it('does not add suffix for EN when count is 1', () => {
      i18nState.locale = 'en';
      const result = tp('app.name', 1);
      expect(result).toBe('Argus');
    });

    it('adds s suffix for EN word ending in normal letter', () => {
      i18nState.locale = 'en';
      // 'conn.connect' -> 'Connect' in EN
      const result = tp('conn.connect', 2);
      expect(result).toBe('Connects');
    });

    it('adds es suffix for EN words ending with x', () => {
      i18nState.locale = 'en';
      // We need a translation ending with x. Use key fallback trick:
      // t('box') returns 'box' (not found in dict)
      const result = tp('box', 3);
      expect(result).toBe('boxes');
    });

    it('adds es suffix for EN words ending with z', () => {
      i18nState.locale = 'en';
      const result = tp('buzz', 2);
      expect(result).toBe('buzzes');
    });
  });

  describe('fmtDate()', () => {
    it('formats date in zh locale', () => {
      i18nState.locale = 'zh';
      const d = new Date(2025, 0, 15); // Jan 15, 2025
      const result = fmtDate(d);
      expect(result).toBe('2025年1月15日');
    });

    it('formats date in en locale', () => {
      i18nState.locale = 'en';
      const d = new Date(2025, 0, 15);
      const result = fmtDate(d);
      // toLocaleDateString('en-US', ...) → "Jan 15, 2025"
      expect(result).toBe('Jan 15, 2025');
    });

    it('accepts string date input', () => {
      i18nState.locale = 'zh';
      const result = fmtDate('2025-06-01T00:00:00');
      expect(result).toContain('2025年');
      expect(result).toContain('6月');
      expect(result).toContain('1日');
    });
  });

  describe('fmtTime()', () => {
    it('formats seconds only (< 60s)', () => {
      expect(fmtTime(45)).toBe('0:45');
    });

    it('formats minutes and seconds', () => {
      expect(fmtTime(125)).toBe('2:05');
    });

    it('formats hours, minutes, and seconds when hours > 0', () => {
      expect(fmtTime(3661)).toBe('1:01:01');
    });

    it('formats exactly 1 hour', () => {
      expect(fmtTime(3600)).toBe('1:00:00');
    });

    it('formats large time with hours', () => {
      // 2h 30m 5s = 9005s
      expect(fmtTime(9005)).toBe('2:30:05');
    });

    it('formats zero seconds', () => {
      expect(fmtTime(0)).toBe('0:00');
    });
  });

  describe('fmtNumber()', () => {
    it('formats number in zh locale', () => {
      i18nState.locale = 'zh';
      const result = fmtNumber(1234.567);
      // zh-CN: "1,234.6" (1 decimal by default)
      expect(result).toContain('1');
      expect(result).toContain('234');
    });

    it('formats number in en locale', () => {
      i18nState.locale = 'en';
      const result = fmtNumber(1234.567);
      expect(result).toContain('1');
      expect(result).toContain('234');
    });

    it('respects custom decimals parameter', () => {
      i18nState.locale = 'en';
      const result = fmtNumber(3.14159, 3);
      expect(result).toBe('3.142');
    });

    it('formats integer with no trailing decimals', () => {
      i18nState.locale = 'en';
      const result = fmtNumber(100, 2);
      // minimumFractionDigits: 0, so no trailing zeros
      expect(result).toBe('100');
    });
  });

  describe('loadLocale()', () => {
    it('reads locale from localStorage and sets it', () => {
      localStorageMock._store['argus_locale'] = 'en';
      loadLocale();
      expect(i18nState.locale).toBe('en');
    });

    it('loads lazy locale from localStorage (triggers async load)', async () => {
      // Use 'ko' which hasn't been loaded by any prior test
      localStorageMock._store['argus_locale'] = 'ko';
      loadLocale();
      expect(i18nState.locale).toBe('ko');
      // Wait for async loader to populate the dict
      await vi.waitFor(() => {
        expect(t('app.name')).toBe('Argus-KO');
      });
    });

    it('loads another lazy locale from localStorage', async () => {
      // Use 'de' to exercise more LOCALE_LOADERS paths
      localStorageMock._store['argus_locale'] = 'de';
      loadLocale();
      expect(i18nState.locale).toBe('de');
      await vi.waitFor(() => {
        expect(t('app.name')).toBe('Argus-DE');
      });
    });

    it('ignores invalid locale value from localStorage', () => {
      localStorageMock._store['argus_locale'] = 'invalid_locale';
      const before = i18nState.locale;
      loadLocale();
      expect(i18nState.locale).toBe(before);
    });

    it('handles missing localStorage value gracefully', () => {
      // No argus_locale in store
      const before = i18nState.locale;
      loadLocale();
      expect(i18nState.locale).toBe(before);
    });
  });

  describe('LOCALE_BETA', () => {
    it('contains all non-primary locales', () => {
      expect(LOCALE_BETA.has('ja')).toBe(true);
      expect(LOCALE_BETA.has('ko')).toBe(true);
      expect(LOCALE_BETA.has('de')).toBe(true);
      expect(LOCALE_BETA.has('fr')).toBe(true);
      expect(LOCALE_BETA.has('es')).toBe(true);
      expect(LOCALE_BETA.has('pt')).toBe(true);
      expect(LOCALE_BETA.has('ru')).toBe(true);
      expect(LOCALE_BETA.has('ar')).toBe(true);
    });

    it('does not contain primary locales', () => {
      expect(LOCALE_BETA.has('zh')).toBe(false);
      expect(LOCALE_BETA.has('en')).toBe(false);
    });
  });

  describe('VALID_LOCALES', () => {
    it('contains all 10 locales', () => {
      expect(VALID_LOCALES).toHaveLength(10);
      expect(VALID_LOCALES).toContain('zh');
      expect(VALID_LOCALES).toContain('en');
      expect(VALID_LOCALES).toContain('ja');
    });
  });
});
