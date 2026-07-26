import React, { useEffect, useState } from 'react';
import { Keyboard, X } from 'lucide-react';

interface Shortcut {
  keys: string[];
  description: string;
  action?: () => void;
}

interface KeyboardShortcutsProps {
  shortcuts?: Shortcut[];
}

/**
 * Keyboard Shortcuts Helper Component
 * Displays available keyboard shortcuts and handles keyboard navigation
 */
export const KeyboardShortcuts: React.FC<KeyboardShortcutsProps> = ({
  shortcuts = defaultShortcuts,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Show shortcuts modal with Ctrl+K or Cmd+K
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      }

      // Close modal with Escape
      if (e.key === 'Escape') {
        setIsOpen(false);
      }

      // Execute registered shortcuts
      shortcuts.forEach((shortcut) => {
        const matches = shortcut.keys.every((key) => {
          if (key === 'Ctrl') return e.ctrlKey;
          if (key === 'Shift') return e.shiftKey;
          if (key === 'Alt') return e.altKey;
          if (key === 'Meta' || key === 'Cmd') return e.metaKey;
          return e.key.toLowerCase() === key.toLowerCase();
        });

        if (matches && shortcut.action) {
          e.preventDefault();
          shortcut.action();
        }
      });
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts]);

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-4 right-4 p-3 bg-blue-600 text-white rounded-full shadow-lg hover:bg-blue-700 transition-colors z-50"
        title="Keyboard Shortcuts (Ctrl+K)"
        aria-label="Show keyboard shortcuts"
      >
        <Keyboard className="w-5 h-5" />
      </button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Keyboard className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900">
                Keyboard Shortcuts
              </h2>
              <p className="text-sm text-gray-600">
                Navigate faster with these shortcuts
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Shortcuts List */}
        <div className="p-6 overflow-y-auto max-h-[calc(80vh-120px)]">
          <div className="space-y-4">
            {shortcuts.map((shortcut, index) => (
              <div
                key={index}
                className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0"
              >
                <span className="text-gray-700">{shortcut.description}</span>
                <div className="flex items-center gap-1">
                  {shortcut.keys.map((key, keyIndex) => (
                    <React.Fragment key={keyIndex}>
                      <kbd className="px-3 py-1.5 bg-gray-100 border border-gray-300 rounded-md text-sm font-mono text-gray-800 shadow-sm">
                        {key}
                      </kbd>
                      {keyIndex < shortcut.keys.length - 1 && (
                        <span className="text-gray-400 text-sm">+</span>
                      )}
                    </React.Fragment>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 bg-gray-50 border-t border-gray-200">
          <p className="text-xs text-gray-500 text-center">
            Press <kbd className="px-2 py-0.5 bg-white border border-gray-300 rounded text-xs">Esc</kbd> or{' '}
            <kbd className="px-2 py-0.5 bg-white border border-gray-300 rounded text-xs">Ctrl+K</kbd> to close
          </p>
        </div>
      </div>
    </div>
  );
};

/**
 * Default keyboard shortcuts for TerraForge Studio
 */
const defaultShortcuts: Shortcut[] = [
  {
    keys: ['Ctrl', 'K'],
    description: 'Show/hide keyboard shortcuts',
  },
  {
    keys: ['Ctrl', 'N'],
    description: 'New terrain generation',
  },
  {
    keys: ['Ctrl', 'S'],
    description: 'Save current configuration',
  },
  {
    keys: ['Ctrl', 'H'],
    description: 'Show generation history',
  },
  {
    keys: ['Ctrl', 'E'],
    description: 'Export terrain',
  },
  {
    keys: ['Ctrl', 'P'],
    description: 'Toggle preview mode',
  },
  {
    keys: ['Ctrl', 'Z'],
    description: 'Undo last action',
  },
  {
    keys: ['Ctrl', 'Shift', 'Z'],
    description: 'Redo last action',
  },
  {
    keys: ['Tab'],
    description: 'Navigate between fields',
  },
  {
    keys: ['Enter'],
    description: 'Generate terrain',
  },
  {
    keys: ['Escape'],
    description: 'Close modal or cancel',
  },
  {
    keys: ['Ctrl', '/'],
    description: 'Show help',
  },
];

export default KeyboardShortcuts;
