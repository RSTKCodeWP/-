import { useEffect, useSyncExternalStore } from 'react';
import { useSettingsStore } from '../stores/settings-store';

/**
 * Applies the correct theme class to <html> based on the user's preference.
 * - 'dark' (default): no class added (CSS variables in :root are dark)
 * - 'light': adds .light class which overrides CSS variables
 * - 'system': follows OS prefers-color-scheme, adds .light when OS is light
 *
 * Call this once at the app root (AppShell).
 */
export function useTheme(): void {
  const theme = useSettingsStore((s) => s.theme);

  useEffect(() => {
    const root = document.documentElement;

    function apply(resolved: 'dark' | 'light') {
      if (resolved === 'light') {
        root.classList.add('light');
      } else {
        root.classList.remove('light');
      }
    }

    if (theme === 'light') {
      apply('light');
      return;
    }

    if (theme === 'dark') {
      apply('dark');
      return;
    }

    // theme === 'system'
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    apply(mq.matches ? 'dark' : 'light');

    function onChange(e: MediaQueryListEvent) {
      apply(e.matches ? 'dark' : 'light');
    }
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [theme]);
}

const mq = window.matchMedia('(prefers-color-scheme: dark)');
function subscribeOS(cb: () => void) {
  mq.addEventListener('change', cb);
  return () => mq.removeEventListener('change', cb);
}
function getOSDark() {
  return mq.matches;
}

/** Returns the currently active theme ('dark' | 'light'). */
export function useResolvedTheme(): 'dark' | 'light' {
  const pref = useSettingsStore((s) => s.theme);
  const osDark = useSyncExternalStore(subscribeOS, getOSDark);
  if (pref === 'dark') return 'dark';
  if (pref === 'light') return 'light';
  return osDark ? 'dark' : 'light';
}
