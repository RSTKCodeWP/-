/**
 * Settings Page - Main settings interface with tabs
 */

import { useState, useEffect } from 'react';
import { Settings, Database, Sliders, FileText, Palette, HardDrive, Brain } from 'lucide-react';
import { settingsApi } from '@/services/settings-api';
import type { UserSettings, SettingsUpdate } from '@/types/settings';

import DataSourcesTab from './DataSourcesTab';
import GenerationTab from './GenerationTab';
import ExportProfilesTab from './ExportProfilesTab';
import UIPreferencesTab from './UIPreferencesTab';
import CacheStorageTab from './CacheStorageTab';
import AITab from './AITab';

interface SettingsPageProps {
  onClose: () => void;
}

type TabId = 'sources' | 'generation' | 'export' | 'ui' | 'cache' | 'ai';

const SettingsPage: React.FC<SettingsPageProps> = ({ onClose }) => {
  const [activeTab, setActiveTab] = useState<TabId>('sources');
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const data = await settingsApi.getSettings();
      setSettings(data);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (updates: SettingsUpdate) => {
    setSaving(true);
    try {
      const updated = await settingsApi.updateSettings(updates);
      setSettings(updated);
      // Show success message (could use toast library)
      alert('Settings saved successfully!');
      
      // Если изменились AI настройки, перезагрузить страницу для применения
      if (updates.ai !== undefined) {
        setTimeout(() => {
          window.location.reload();
        }, 1000);
      }
    } catch (error) {
      console.error('Failed to save settings:', error);
      alert('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading || !settings) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="glass rounded-lg p-8">
          <div className="animate-spin w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full" />
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'sources' as TabId, label: 'Data Sources', icon: Database },
    { id: 'generation' as TabId, label: 'Generation', icon: Sliders },
    { id: 'export' as TabId, label: 'Export Profiles', icon: FileText },
    { id: 'ai' as TabId, label: 'AI Assistant', icon: Brain },
    { id: 'ui' as TabId, label: 'UI & Language', icon: Palette },
    { id: 'cache' as TabId, label: 'Storage', icon: HardDrive },
  ];

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="glass rounded-lg shadow-2xl max-w-5xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-3">
            <Settings className="w-6 h-6 text-blue-600 dark:text-blue-400" />
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Settings</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 text-2xl transition"
          >
            ×
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar Tabs */}
          <div className="w-64 border-r border-gray-200 dark:border-gray-700 p-4 space-y-2">
            {tabs.map(tab => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg transition ${
                    activeTab === tab.id
                      ? 'bg-blue-600 text-white'
                      : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium">{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Content Area */}
          <div className="flex-1 p-6 overflow-y-auto bg-white/50 dark:bg-gray-900/50">
            {activeTab === 'sources' && (
              <DataSourcesTab
                credentials={settings.credentials}
                onSave={(credentials) => handleSave({ credentials })}
                saving={saving}
              />
            )}

            {activeTab === 'generation' && (
              <GenerationTab
                generation={settings.generation}
                onSave={(generation) => handleSave({ generation })}
                saving={saving}
              />
            )}

            {activeTab === 'export' && (
              <ExportProfilesTab
                profiles={settings.export_profiles}
                onSave={(export_profiles) => handleSave({ export_profiles })}
                saving={saving}
              />
            )}

            {activeTab === 'ui' && (
              <UIPreferencesTab
                ui={settings.ui}
                onSave={(ui) => handleSave({ ui })}
                saving={saving}
              />
            )}

            {activeTab === 'ai' && (
              <AITab
                settings={settings.ai || { enabled: false, ollama_url: 'http://localhost:11434', vision_model: 'qwen3-vl:235b-cloud', coder_model: 'qwen3-coder:480b-cloud', auto_analyze: false, timeout_seconds: 120 }}
                onSave={(ai) => handleSave({ ai })}
                saving={saving}
              />
            )}

            {activeTab === 'cache' && (
              <CacheStorageTab
                cache={settings.cache}
                onSave={(cache) => handleSave({ cache })}
                saving={saving}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
