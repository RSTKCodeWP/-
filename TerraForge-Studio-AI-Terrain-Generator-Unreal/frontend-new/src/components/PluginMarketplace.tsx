/**
 * Installed plugins panel.
 *
 * Backed by the real /api/plugins endpoints. An earlier version of this
 * component rendered a hardcoded plugin with invented download counts and a
 * non-functional Install button, so nothing it displayed was real.
 */

import { useCallback, useEffect, useState } from 'react';
import { Plug, Power, PowerOff, RefreshCw, Search, X } from 'lucide-react';
import { api } from '@/services/api';
import { notify } from '@/utils/toast';

interface Plugin {
  name: string;
  version: string;
  author: string;
  description: string;
  enabled: boolean;
}

interface PluginMarketplaceProps {
  onClose: () => void;
}

const PluginMarketplace: React.FC<PluginMarketplaceProps> = ({ onClose }) => {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadPlugins = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get<{ plugins: Plugin[]; count: number }>('/api/plugins/list');
      setPlugins(response.data.plugins);
    } catch {
      setError('Could not load plugins');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPlugins();
  }, [loadPlugins]);

  const toggle = async (plugin: Plugin) => {
    const action = plugin.enabled ? 'disable' : 'enable';
    setBusy(plugin.name);
    try {
      await api.post(`/api/plugins/${encodeURIComponent(plugin.name)}/${action}`);
      // Reflect the change locally rather than refetching the whole list.
      setPlugins((current) =>
        current.map((item) =>
          item.name === plugin.name ? { ...item, enabled: !item.enabled } : item,
        ),
      );
      notify.success(`Plugin ${plugin.name} ${action}d`);
    } catch {
      notify.error(`Could not ${action} ${plugin.name}`);
    } finally {
      setBusy(null);
    }
  };

  const reload = async () => {
    setBusy('__reload__');
    try {
      await api.post('/api/plugins/reload');
      await loadPlugins();
      notify.success('Plugins reloaded');
    } catch {
      notify.error('Could not reload plugins');
    } finally {
      setBusy(null);
    }
  };

  const needle = query.trim().toLowerCase();
  const visible = needle
    ? plugins.filter(
        (plugin) =>
          plugin.name.toLowerCase().includes(needle) ||
          plugin.description.toLowerCase().includes(needle),
      )
    : plugins;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-lg bg-white shadow-xl dark:bg-gray-900">
        <div className="flex items-center justify-between border-b border-gray-200 p-4 dark:border-gray-700">
          <h2 className="flex items-center gap-2 text-xl font-semibold text-gray-900 dark:text-white">
            <Plug className="h-5 w-5" />
            Plugins
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={reload}
              disabled={busy !== null}
              className="rounded-md p-2 text-gray-500 hover:bg-gray-100 disabled:opacity-50 dark:hover:bg-gray-800"
              title="Reload plugins from disk"
            >
              <RefreshCw className={`h-4 w-4 ${busy === '__reload__' ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="rounded-md p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="border-b border-gray-200 p-4 dark:border-gray-700">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Filter plugins..."
              className="w-full rounded-lg border border-gray-300 py-2 pl-9 pr-3 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
            />
          </div>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {loading && <p className="text-sm text-gray-500">Loading...</p>}

          {error && !loading && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-200">
              {error}
            </div>
          )}

          {!loading && !error && visible.length === 0 && (
            <div className="py-8 text-center text-sm text-gray-500">
              {plugins.length === 0 ? (
                <>
                  <p>No plugins installed.</p>
                  <p className="mt-1">
                    Drop a plugin package into the configured plugin directory and press reload.
                  </p>
                </>
              ) : (
                <p>Nothing matches &ldquo;{query}&rdquo;.</p>
              )}
            </div>
          )}

          {visible.map((plugin) => (
            <div
              key={plugin.name}
              className="rounded-lg border border-gray-200 p-4 dark:border-gray-700"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h3 className="truncate font-semibold text-gray-900 dark:text-white">
                    {plugin.name}
                    <span className="ml-2 text-xs font-normal text-gray-500">v{plugin.version}</span>
                  </h3>
                  <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                    {plugin.description}
                  </p>
                  <p className="mt-1 text-xs text-gray-500">by {plugin.author}</p>
                </div>

                <button
                  onClick={() => toggle(plugin)}
                  disabled={busy !== null}
                  className={`flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition disabled:opacity-50 ${
                    plugin.enabled
                      ? 'bg-green-100 text-green-800 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-200'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300'
                  }`}
                >
                  {plugin.enabled ? (
                    <>
                      <Power className="h-3.5 w-3.5" /> Enabled
                    </>
                  ) : (
                    <>
                      <PowerOff className="h-3.5 w-3.5" /> Disabled
                    </>
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default PluginMarketplace;
