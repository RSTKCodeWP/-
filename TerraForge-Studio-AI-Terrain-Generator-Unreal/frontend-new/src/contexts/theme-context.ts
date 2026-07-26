/**
 * Theme context object and its types.
 *
 * Kept separate from the provider component so that ThemeContext.tsx exports
 * only a component: mixing component and non-component exports in one module
 * makes React Fast Refresh fall back to a full page reload for that file.
 */

import { createContext } from 'react';

export type Theme = 'light' | 'dark' | 'auto';
export type ResolvedTheme = 'light' | 'dark';

export interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  /** The theme actually applied, with 'auto' resolved against the OS setting. */
  resolvedTheme: ResolvedTheme;
}

export const STORAGE_KEY = 'terraforge-theme';

export const ThemeContext = createContext<ThemeContextType | undefined>(undefined);
