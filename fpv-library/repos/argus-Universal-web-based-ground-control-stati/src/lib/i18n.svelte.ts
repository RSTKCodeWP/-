export type Locale = 'zh' | 'en' | 'ja' | 'ko' | 'de' | 'fr' | 'es' | 'pt' | 'ru' | 'ar';

class I18nState {
  locale: Locale = $state('zh');
}

export const i18nState = new I18nState();

import zh from './locales/zh';
import en from './locales/en';

let _dictVersion = $state(0);
const loadedDicts: Partial<Record<Locale, Record<string, string>>> = { zh, en };

const LOCALE_LOADERS: Record<Locale, () => Promise<{ default: Record<string, string> }>> = {
  zh: () => Promise.resolve({ default: zh }),
  en: () => Promise.resolve({ default: en }),
  ja: () => import('./locales/ja'),
  ko: () => import('./locales/ko'),
  de: () => import('./locales/de'),
  fr: () => import('./locales/fr'),
  es: () => import('./locales/es'),
  pt: () => import('./locales/pt'),
  ru: () => import('./locales/ru'),
  ar: () => import('./locales/ar'),
};

function getDict(locale: Locale): Record<string, string> {
  void _dictVersion;
  return loadedDicts[locale] || zh;
}

export function t(key: string): string {
  return getDict(i18nState.locale)[key] || zh[key] || key;
}

export function setLocale(l: Locale) {
  i18nState.locale = l;
  try {
    localStorage.setItem('argus_locale', l);
  } catch {}
  if (!loadedDicts[l]) {
    LOCALE_LOADERS[l]()
      .then((mod) => {
        loadedDicts[l] = mod.default;
        _dictVersion++;
      })
      .catch(() => {});
  }
  _syncCallback?.(l);
}

let _syncCallback: ((l: Locale) => void) | null = null;
export function onLocaleChange(cb: (l: Locale) => void) {
  _syncCallback = cb;
}

export function getLocale(): Locale {
  return i18nState.locale;
}

export function tp(key: string, count: number): string {
  const tmpl = t(key);
  const replaced = tmpl.replace('{n}', String(count));
  if (i18nState.locale === 'en' && count !== 1) {
    return replaced.replace(/(\w+)$/, (m) => {
      if (m.endsWith('s') || m.endsWith('x') || m.endsWith('z')) return m + 'es';
      return m + 's';
    });
  }
  return replaced;
}

export function fmtDate(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  const localeMap: Record<string, string> = {
    zh: 'zh-CN',
    en: 'en-US',
    ja: 'ja-JP',
    ko: 'ko-KR',
    de: 'de-DE',
    fr: 'fr-FR',
    es: 'es-ES',
    pt: 'pt-BR',
    ru: 'ru-RU',
    ar: 'ar-SA',
  };
  return d.toLocaleDateString(localeMap[i18nState.locale] || 'en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function fmtTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function fmtNumber(n: number, decimals = 1): string {
  return n.toLocaleString(i18nState.locale === 'zh' ? 'zh-CN' : 'en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  });
}

const VALID_LOCALES: Locale[] = ['zh', 'en', 'ja', 'ko', 'de', 'fr', 'es', 'pt', 'ru', 'ar'];
export { VALID_LOCALES };

export const LOCALE_BETA: Set<Locale> = new Set(['ja', 'ko', 'de', 'fr', 'es', 'pt', 'ru', 'ar']);

export function loadLocale() {
  try {
    const saved = localStorage.getItem('argus_locale');
    if (saved && VALID_LOCALES.includes(saved as Locale)) {
      i18nState.locale = saved as Locale;
      if (!loadedDicts[saved as Locale]) {
        LOCALE_LOADERS[saved as Locale]()
          .then((mod) => {
            loadedDicts[saved as Locale] = mod.default;
            _dictVersion++;
          })
          .catch(() => {});
      }
    }
  } catch {}
}
