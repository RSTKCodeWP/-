import type { Theme } from '../../hooks/useTheme';
import { useState } from 'react';
import { Loader } from 'lucide-react';
import type { UIPreferences } from '@/types/settings';
import { useTheme } from '@/hooks/useTheme';
import { useTranslation } from 'react-i18next';

interface UIPreferencesTabProps {
  ui: UIPreferences;
  onSave: (ui: UIPreferences) => void;
  saving: boolean;
}

const UIPreferencesTab: React.FC<UIPreferencesTabProps> = ({ ui, onSave, saving }) => {
  const defaultUI: UIPreferences = {
    language: 'en',
    theme: 'auto',
    show_tooltips: false,
    show_tutorial: true,
    compact_mode: false,
    default_map_view: '2d',
  };

  const [formData, setFormData] = useState<UIPreferences>({
    ...defaultUI,
    ...ui,
  });
  const { theme, setTheme } = useTheme();
  const { i18n } = useTranslation();

  const handleSave = () => {
    // Apply theme change immediately
    setTheme(formData.theme);
    // Apply language change immediately
    i18n.changeLanguage(formData.language);
    onSave(formData);
  };

  return (
    <div className="space-y-6">
      <h3 className="text-xl font-semibold text-gray-900 dark:text-white">UI & Language Preferences</h3>

      <div className="grid grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Language</label>
          <select
            value={formData.language}
            onChange={(e) => setFormData({ ...formData, language: e.target.value as 'en' | 'ru' })}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
          >
            <option value="en">English</option>
            <option value="ru">Русский</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Theme</label>
          <select
            value={formData.theme}
            onChange={(e) => setFormData({ ...formData, theme: e.target.value as Theme })}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
          >
            <option value="light">Light</option>
            <option value="dark">Dark</option>
            <option value="auto">Auto (Follow System)</option>
          </select>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Current: {theme === 'auto' ? `Auto (${window.matchMedia('(prefers-color-scheme: dark)').matches ? 'Dark' : 'Light'})` : theme}
          </p>
        </div>
      </div>

      <div className="flex justify-end pt-6 border-t border-gray-200 dark:border-gray-700">
        <button 
          onClick={handleSave} 
          disabled={saving} 
          className="flex items-center px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition"
        >
          {saving && <Loader className="w-4 h-4 animate-spin mr-2" />}
          Save Preferences
        </button>
      </div>
    </div>
  );
};

export default UIPreferencesTab;
