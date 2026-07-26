/**
 * Keyboard Shortcuts Hook
 * Handles global keyboard shortcuts for the application
 */

import { useEffect } from 'react';

type ShortcutHandler = () => void;

interface ShortcutMap {
  [key: string]: ShortcutHandler;
}

export function useKeyboardShortcuts(shortcuts: ShortcutMap) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase();
      const ctrl = event.ctrlKey || event.metaKey; // Support both Ctrl and Cmd
      const shift = event.shiftKey;
      const alt = event.altKey;

      // Build shortcut string
      let shortcut = '';
      if (ctrl) shortcut += 'ctrl+';
      if (shift) shortcut += 'shift+';
      if (alt) shortcut += 'alt+';
      shortcut += key;

      // Check if shortcut exists and execute
      if (shortcuts[shortcut]) {
        event.preventDefault();
        shortcuts[shortcut]();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts]);
}

/**
 * Get formatted shortcut display text
 */
export function getShortcutDisplay(shortcut: string): string {
  const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
  
  return shortcut
    .split('+')
    .map(key => {
      if (key === 'ctrl') return isMac ? '⌘' : 'Ctrl';
      if (key === 'shift') return isMac ? '⇧' : 'Shift';
      if (key === 'alt') return isMac ? '⌥' : 'Alt';
      return key.toUpperCase();
    })
    .join(isMac ? '' : '+');
}

