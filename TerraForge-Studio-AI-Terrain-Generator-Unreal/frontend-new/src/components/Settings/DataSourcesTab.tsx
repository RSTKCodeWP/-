/**
 * Data Sources Settings Tab
 */

import { useState } from 'react';
import { AlertCircle, Check, X, Loader, Eye, EyeOff } from 'lucide-react';
import { settingsApi } from '@/services/settings-api';
import type { DataSourceCredentials } from '@/types/settings';

interface TestResult {
  success: boolean;
  message: string;
  /** Null when no request was attempted (source disabled or unconfigured). */
  reachable: boolean | null;
}

/**
 * Outcome of a connectivity probe.
 *
 * Three states, not two: a source that was never contacted is neither a pass
 * nor a failure, and showing it in red would misreport it.
 */
const ConnectionStatus: React.FC<{ result?: TestResult }> = ({ result }) => {
  if (!result) return null;

  if (result.reachable === null) {
    return (
      <div className="flex items-center space-x-2 text-sm text-amber-700 dark:text-amber-400">
        <AlertCircle className="w-4 h-4" />
        <span>{result.message}</span>
      </div>
    );
  }

  return (
    <div
      className={`flex items-center space-x-2 text-sm ${
        result.success ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'
      }`}
    >
      {result.success ? <Check className="w-4 h-4" /> : <X className="w-4 h-4" />}
      <span>{result.message}</span>
    </div>
  );
};

interface DataSourcesTabProps {
  credentials: DataSourceCredentials;
  onSave: (credentials: DataSourceCredentials) => void;
  saving: boolean;
}

const DataSourcesTab: React.FC<DataSourcesTabProps> = ({ credentials, onSave, saving }) => {
  // Provide default values if credentials are incomplete
  const defaultCredentials: DataSourceCredentials = {
    sentinelhub: {
      enabled: false,
      client_id: '',
      client_secret: '',
    },
    opentopography: {
      enabled: false,
      api_key: '',
    },
    azure_maps: {
      enabled: false,
      subscription_key: '',
    },
    google_earth_engine: {
      enabled: false,
      service_account: '',
      private_key_path: '',
    },
  };

  const [formData, setFormData] = useState<DataSourceCredentials>({
    ...defaultCredentials,
    ...credentials,
    sentinelhub: { ...defaultCredentials.sentinelhub, ...credentials?.sentinelhub },
    opentopography: { ...defaultCredentials.opentopography, ...credentials?.opentopography },
    azure_maps: { ...defaultCredentials.azure_maps, ...credentials?.azure_maps },
    google_earth_engine: { ...defaultCredentials.google_earth_engine, ...credentials?.google_earth_engine },
  });
  const [testing, setTesting] = useState<Record<string, boolean>>({});
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});

  const handleTest = async (source: string) => {
    setTesting(prev => ({ ...prev, [source]: true }));
    try {
      const result = await settingsApi.testConnection(source);
      setTestResults(prev => ({
        ...prev,
        [source]: {
          success: result.success,
          message: result.message,
          reachable: result.reachable,
        }
      }));
    } catch {
      setTestResults(prev => ({
        ...prev,
        [source]: { success: false, message: 'Connection failed', reachable: false }
      }));
    } finally {
      setTesting(prev => ({ ...prev, [source]: false }));
    }
  };

  const toggleSecret = (key: string) => {
    setShowSecrets(prev => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="space-y-8">
      <div>
        <h3 className="text-xl font-semibold mb-2">Data Source Credentials</h3>
        <p className="text-sm text-gray-600">
          Configure API keys for premium data sources. Leave empty to use free sources (OSM + SRTM).
        </p>
      </div>

      {/* Sentinel Hub */}
      <div className="bg-white rounded-lg p-6 border border-gray-200 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="font-semibold text-lg">Sentinel Hub</h4>
            <p className="text-sm text-gray-600">High-resolution satellite imagery (10-60m)</p>
          </div>
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.sentinelhub.enabled}
              onChange={(e) => setFormData({
                ...formData,
                sentinelhub: { ...formData.sentinelhub, enabled: e.target.checked }
              })}
              className="rounded text-blue-600"
            />
            <span className="ml-2 text-sm">Enabled</span>
          </label>
        </div>

        {formData.sentinelhub.enabled && (
          <div className="space-y-3 pt-4 border-t">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Client ID
              </label>
              <div className="relative">
                <input
                  type={showSecrets['sh_id'] ? 'text' : 'password'}
                  value={formData.sentinelhub.client_id || ''}
                  onChange={(e) => setFormData({
                    ...formData,
                    sentinelhub: { ...formData.sentinelhub, client_id: e.target.value }
                  })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md pr-10"
                  placeholder="your-client-id"
                />
                <button
                  type="button"
                  onClick={() => toggleSecret('sh_id')}
                  className="absolute right-2 top-2.5 text-gray-500"
                >
                  {showSecrets['sh_id'] ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Client Secret
              </label>
              <div className="relative">
                <input
                  type={showSecrets['sh_secret'] ? 'text' : 'password'}
                  value={formData.sentinelhub.client_secret || ''}
                  onChange={(e) => setFormData({
                    ...formData,
                    sentinelhub: { ...formData.sentinelhub, client_secret: e.target.value }
                  })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md pr-10"
                  placeholder="your-client-secret"
                />
                <button
                  type="button"
                  onClick={() => toggleSecret('sh_secret')}
                  className="absolute right-2 top-2.5 text-gray-500"
                >
                  {showSecrets['sh_secret'] ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <button
              onClick={() => handleTest('sentinelhub')}
              disabled={testing['sentinelhub']}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200 disabled:opacity-50"
            >
              {testing['sentinelhub'] ? (
                <Loader className="w-4 h-4 animate-spin" />
              ) : (
                <Check className="w-4 h-4" />
              )}
              <span>Test Connection</span>
            </button>

            <ConnectionStatus result={testResults['sentinelhub']} />
          </div>
        )}
      </div>

      {/* OpenTopography */}
      <div className="bg-white rounded-lg p-6 border border-gray-200 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="font-semibold text-lg">OpenTopography</h4>
            <p className="text-sm text-gray-600">High-resolution DEMs (0.5-30m, LiDAR)</p>
          </div>
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.opentopography.enabled}
              onChange={(e) => setFormData({
                ...formData,
                opentopography: { ...formData.opentopography, enabled: e.target.checked }
              })}
              className="rounded text-blue-600"
            />
            <span className="ml-2 text-sm">Enabled</span>
          </label>
        </div>

        {formData.opentopography.enabled && (
          <div className="space-y-3 pt-4 border-t">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                API Key
              </label>
              <div className="relative">
                <input
                  type={showSecrets['ot_key'] ? 'text' : 'password'}
                  value={formData.opentopography.api_key || ''}
                  onChange={(e) => setFormData({
                    ...formData,
                    opentopography: { ...formData.opentopography, api_key: e.target.value }
                  })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md pr-10"
                  placeholder="your-api-key"
                />
                <button
                  type="button"
                  onClick={() => toggleSecret('ot_key')}
                  className="absolute right-2 top-2.5 text-gray-500"
                >
                  {showSecrets['ot_key'] ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Get your free key at <a href="https://opentopography.org" target="_blank" rel="noopener" className="text-blue-600 hover:underline">opentopography.org</a>
              </p>
            </div>

            <button
              onClick={() => handleTest('opentopography')}
              disabled={testing['opentopography']}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200 disabled:opacity-50"
            >
              {testing['opentopography'] ? (
                <Loader className="w-4 h-4 animate-spin" />
              ) : (
                <Check className="w-4 h-4" />
              )}
              <span>Test Connection</span>
            </button>

            <ConnectionStatus result={testResults['opentopography']} />
          </div>
        )}
      </div>

      {/* Azure Maps */}
      <div className="bg-white rounded-lg p-6 border border-gray-200 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="font-semibold text-lg">Azure Maps</h4>
            <p className="text-sm text-gray-600">Vector data + elevation (Microsoft Azure)</p>
          </div>
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.azure_maps.enabled}
              onChange={(e) => setFormData({
                ...formData,
                azure_maps: { ...formData.azure_maps, enabled: e.target.checked }
              })}
              className="rounded text-blue-600"
            />
            <span className="ml-2 text-sm">Enabled</span>
          </label>
        </div>

        {formData.azure_maps.enabled && (
          <div className="space-y-3 pt-4 border-t">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Subscription Key
              </label>
              <div className="relative">
                <input
                  type={showSecrets['az_key'] ? 'text' : 'password'}
                  value={formData.azure_maps.subscription_key || ''}
                  onChange={(e) => setFormData({
                    ...formData,
                    azure_maps: { ...formData.azure_maps, subscription_key: e.target.value }
                  })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md pr-10"
                  placeholder="your-subscription-key"
                />
                <button
                  type="button"
                  onClick={() => toggleSecret('az_key')}
                  className="absolute right-2 top-2.5 text-gray-500"
                >
                  {showSecrets['az_key'] ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <button
              onClick={() => handleTest('azure_maps')}
              disabled={testing['azure_maps']}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200 disabled:opacity-50"
            >
              {testing['azure_maps'] ? (
                <Loader className="w-4 h-4 animate-spin" />
              ) : (
                <Check className="w-4 h-4" />
              )}
              <span>Test Connection</span>
            </button>

            <ConnectionStatus result={testResults['azure_maps']} />
          </div>
        )}
      </div>

      {/* Google Earth Engine */}
      <div className="bg-white rounded-lg p-6 border border-gray-200 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="font-semibold text-lg">Google Earth Engine</h4>
            <p className="text-sm text-gray-600">Global satellite data archive (Google Cloud)</p>
          </div>
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.google_earth_engine.enabled}
              onChange={(e) => setFormData({
                ...formData,
                google_earth_engine: { ...formData.google_earth_engine, enabled: e.target.checked }
              })}
              className="rounded text-blue-600"
            />
            <span className="ml-2 text-sm">Enabled</span>
          </label>
        </div>

        {formData.google_earth_engine.enabled && (
          <div className="space-y-3 pt-4 border-t">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Service Account Email
              </label>
              <div className="relative">
                <input
                  type={showSecrets['gee_account'] ? 'text' : 'password'}
                  value={formData.google_earth_engine.service_account || ''}
                  onChange={(e) => setFormData({
                    ...formData,
                    google_earth_engine: { ...formData.google_earth_engine, service_account: e.target.value }
                  })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md pr-10"
                  placeholder="your-service-account@project.iam.gserviceaccount.com"
                />
                <button
                  type="button"
                  onClick={() => toggleSecret('gee_account')}
                  className="absolute right-2 top-2.5 text-gray-500"
                >
                  {showSecrets['gee_account'] ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Private Key Path
              </label>
              <input
                type="text"
                value={formData.google_earth_engine.private_key_path || ''}
                onChange={(e) => setFormData({
                  ...formData,
                  google_earth_engine: { ...formData.google_earth_engine, private_key_path: e.target.value }
                })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
                placeholder="/path/to/private-key.json"
              />
              <p className="text-xs text-gray-500 mt-1">
                Path to your Google Cloud service account JSON key file
              </p>
            </div>

            <button
              onClick={() => handleTest('google_earth_engine')}
              disabled={testing['google_earth_engine']}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200 disabled:opacity-50"
            >
              {testing['google_earth_engine'] ? (
                <Loader className="w-4 h-4 animate-spin" />
              ) : (
                <Check className="w-4 h-4" />
              )}
              <span>Test Connection</span>
            </button>

            <ConnectionStatus result={testResults['google_earth_engine']} />
          </div>
        )}
      </div>

      {/* Save Button */}
      <div className="flex justify-end pt-6 border-t">
        <button
          onClick={() => onSave(formData)}
          disabled={saving}
          className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center space-x-2"
        >
          {saving && <Loader className="w-4 h-4 animate-spin" />}
          <span>Save Credentials</span>
        </button>
      </div>
    </div>
  );
};

export default DataSourcesTab;

