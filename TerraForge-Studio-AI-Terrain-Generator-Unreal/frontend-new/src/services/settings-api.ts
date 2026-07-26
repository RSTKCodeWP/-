/**
 * Settings API Service
 */

import { api } from './api';
import type {
  UserSettings,
  SettingsUpdate,
  MaskedCredentials,
  ConnectionTestResult,
} from '@/types/settings';

export const settingsApi = {
  // Get current settings
  getSettings: async (): Promise<UserSettings> => {
    const response = await api.get<UserSettings>('/api/settings/');
    return response.data;
  },

  // Get masked credentials (for display)
  getMaskedCredentials: async (): Promise<MaskedCredentials> => {
    const response = await api.get<MaskedCredentials>('/api/settings/masked');
    return response.data;
  },

  // Update settings
  updateSettings: async (updates: SettingsUpdate): Promise<UserSettings> => {
    const response = await api.post<UserSettings>('/api/settings/', updates);
    return response.data;
  },

  // Test connection to data source
  testConnection: async (source: string): Promise<ConnectionTestResult> => {
    const response = await api.post<ConnectionTestResult>(
      `/api/settings/test-connection/${source}`
    );
    return response.data;
  },

  // Export settings
  exportSettings: async (includeCredentials: boolean = false): Promise<Record<string, unknown>> => {
    const response = await api.get('/api/settings/export', {
      params: { include_credentials: includeCredentials },
    });
    return response.data;
  },

  // Import settings
  importSettings: async (data: Record<string, unknown>): Promise<UserSettings> => {
    const response = await api.post<UserSettings>('/api/settings/import', data);
    return response.data;
  },

  // Reset to defaults
  resetSettings: async (): Promise<UserSettings> => {
    const response = await api.post<UserSettings>('/api/settings/reset');
    return response.data;
  },

  // Check if first run
  checkFirstRun: async (): Promise<{ first_run: boolean; show_wizard: boolean }> => {
    const response = await api.get('/api/settings/first-run');
    return response.data;
  },

  // Complete wizard
  completeWizard: async (): Promise<{ success: boolean; message: string }> => {
    const response = await api.post('/api/settings/complete-wizard');
    return response.data;
  },
};

export default settingsApi;

