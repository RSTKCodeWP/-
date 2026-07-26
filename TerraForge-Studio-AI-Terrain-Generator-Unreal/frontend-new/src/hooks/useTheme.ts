/**
 * Access the current theme and the setter that persists it.
 *
 * Throws when used outside a ThemeProvider, so a missing provider surfaces
 * immediately instead of silently rendering with undefined values.
 */

import { useContext } from 'react';

import { ThemeContext, type ThemeContextType } from '../contexts/theme-context';

export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

export type { Theme, ResolvedTheme } from '../contexts/theme-context';
