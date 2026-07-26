/**
 * Cache Manager Component
 * UI for managing terrain generation cache
 */

import { useState, useEffect } from 'react';
import { Database, Trash2, RefreshCw, HardDrive, Clock, TrendingUp, X } from 'lucide-react';
import { motion } from 'framer-motion';
import { notify } from '../utils/toast';

interface CacheStats {
  total_entries: number;
  total_size_mb: number;
  max_size_mb: number;
  max_age_days: number;
  oldest_entry: string | null;
  most_accessed: string | null;
}

interface CacheEntry {
  key: string;
  size_mb: number;
  created: string;
  last_accessed: string;
  access_count: number;
  preview?: string;
}

interface CacheManagerProps {
  onClose: () => void;
}

export default function CacheManager({ onClose }: CacheManagerProps) {
  const [stats, setStats] = useState<CacheStats | null>(null);
  const [entries, setEntries] = useState<CacheEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadCacheData();
  }, []);

  const loadCacheData = async () => {
    setLoading(true);
    try {
      // Fetch cache statistics
      const statsResponse = await fetch('/api/cache/stats');
      if (statsResponse.ok) {
        const statsData = await statsResponse.json();
        setStats(statsData);
      }

      // Fetch cache entries
      const entriesResponse = await fetch('/api/cache/entries');
      if (entriesResponse.ok) {
        const entriesData = await entriesResponse.json();
        setEntries(entriesData.entries || []);
      }
    } catch (error) {
      console.error('Failed to load cache data:', error);
      notify.error('Failed to load cache data');
    } finally {
      setLoading(false);
    }
  };

  const handleClearAll = async () => {
    if (!confirm('Clear entire cache? This will remove all cached terrain generations.')) {
      return;
    }

    try {
      const response = await fetch('/api/cache/clear', { method: 'POST' });
      if (response.ok) {
        notify.success('Cache cleared successfully');
        loadCacheData();
        setSelectedKeys(new Set());
      } else {
        throw new Error('Failed to clear cache');
      }
    } catch (error) {
      console.error('Failed to clear cache:', error);
      notify.error('Failed to clear cache');
    }
  };

  const handleDeleteSelected = async () => {
    if (selectedKeys.size === 0) {
      notify.error('No entries selected');
      return;
    }

    if (!confirm(`Delete ${selectedKeys.size} selected cache ${selectedKeys.size === 1 ? 'entry' : 'entries'}?`)) {
      return;
    }

    try {
      const deletePromises = Array.from(selectedKeys).map(key =>
        fetch(`/api/cache/${key}`, { method: 'DELETE' })
      );

      await Promise.all(deletePromises);
      notify.success(`Deleted ${selectedKeys.size} cache ${selectedKeys.size === 1 ? 'entry' : 'entries'}`);
      loadCacheData();
      setSelectedKeys(new Set());
    } catch (error) {
      console.error('Failed to delete cache entries:', error);
      notify.error('Failed to delete cache entries');
    }
  };

  const toggleSelection = (key: string) => {
    const newSelected = new Set(selectedKeys);
    if (newSelected.has(key)) {
      newSelected.delete(key);
    } else {
      newSelected.add(key);
    }
    setSelectedKeys(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedKeys.size === entries.length) {
      setSelectedKeys(new Set());
    } else {
      setSelectedKeys(new Set(entries.map(e => e.key)));
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    } catch {
      return dateStr;
    }
  };

  const formatSize = (mb: number) => {
    if (mb > 1000) {
      return `${(mb / 1024).toFixed(2)} GB`;
    }
    return `${mb.toFixed(2)} MB`;
  };

  const getCacheUsagePercentage = () => {
    if (!stats) return 0;
    return (stats.total_size_mb / stats.max_size_mb) * 100;
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-hidden"
      >
        {/* Header */}
        <div className="bg-gradient-to-r from-purple-600 to-indigo-600 text-white p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <Database className="w-8 h-8" />
              <div>
                <h2 className="text-2xl font-bold">Cache Manager</h2>
                <p className="text-purple-100 text-sm">
                  Manage cached terrain generations
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white hover:bg-opacity-20 rounded-lg transition"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Quick Stats */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white bg-opacity-20 rounded-lg p-3">
                <div className="flex items-center space-x-2 mb-1">
                  <Database className="w-4 h-4" />
                  <span className="text-xs opacity-90">Entries</span>
                </div>
                <div className="text-2xl font-bold">{stats.total_entries}</div>
              </div>
              
              <div className="bg-white bg-opacity-20 rounded-lg p-3">
                <div className="flex items-center space-x-2 mb-1">
                  <HardDrive className="w-4 h-4" />
                  <span className="text-xs opacity-90">Size</span>
                </div>
                <div className="text-2xl font-bold">{formatSize(stats.total_size_mb)}</div>
              </div>
              
              <div className="bg-white bg-opacity-20 rounded-lg p-3">
                <div className="flex items-center space-x-2 mb-1">
                  <TrendingUp className="w-4 h-4" />
                  <span className="text-xs opacity-90">Usage</span>
                </div>
                <div className="text-2xl font-bold">{getCacheUsagePercentage().toFixed(0)}%</div>
              </div>
              
              <div className="bg-white bg-opacity-20 rounded-lg p-3">
                <div className="flex items-center space-x-2 mb-1">
                  <Clock className="w-4 h-4" />
                  <span className="text-xs opacity-90">Max Age</span>
                </div>
                <div className="text-2xl font-bold">{stats.max_age_days}d</div>
              </div>
            </div>
          )}

          {/* Usage Bar */}
          {stats && (
            <div className="mt-4">
              <div className="flex items-center justify-between text-xs mb-1">
                <span>Storage Usage</span>
                <span>{formatSize(stats.total_size_mb)} / {formatSize(stats.max_size_mb)}</span>
              </div>
              <div className="w-full bg-white bg-opacity-20 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${
                    getCacheUsagePercentage() > 90 ? 'bg-red-400' :
                    getCacheUsagePercentage() > 70 ? 'bg-yellow-400' :
                    'bg-green-400'
                  }`}
                  style={{ width: `${Math.min(getCacheUsagePercentage(), 100)}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Actions Bar */}
        <div className="bg-gray-50 dark:bg-gray-750 border-b border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <button
                onClick={loadCacheData}
                className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
              >
                <RefreshCw className="w-4 h-4" />
                <span>Refresh</span>
              </button>
              
              {entries.length > 0 && (
                <button
                  onClick={toggleSelectAll}
                  className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition"
                >
                  {selectedKeys.size === entries.length ? 'Deselect All' : 'Select All'}
                </button>
              )}
            </div>

            <div className="flex items-center space-x-2">
              {selectedKeys.size > 0 && (
                <button
                  onClick={handleDeleteSelected}
                  className="flex items-center space-x-2 px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition"
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Delete Selected ({selectedKeys.size})</span>
                </button>
              )}
              
              <button
                onClick={handleClearAll}
                className="flex items-center space-x-2 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition"
              >
                <Trash2 className="w-4 h-4" />
                <span>Clear All</span>
              </button>
            </div>
          </div>
        </div>

        {/* Cache Entries */}
        <div className="p-6 overflow-y-auto" style={{ maxHeight: 'calc(90vh - 350px)' }}>
          {loading ? (
            <div className="text-center py-12">
              <RefreshCw className="w-12 h-12 mx-auto text-gray-400 animate-spin mb-4" />
              <p className="text-gray-500 dark:text-gray-400">Loading cache data...</p>
            </div>
          ) : entries.length === 0 ? (
            <div className="text-center py-12">
              <Database className="w-16 h-16 mx-auto text-gray-300 dark:text-gray-600 mb-4" />
              <p className="text-gray-500 dark:text-gray-400 text-lg">No cached entries</p>
              <p className="text-sm text-gray-400 dark:text-gray-500 mt-2">
                Cache will be populated as you generate terrain
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {entries.map((entry) => (
                <motion.div
                  key={entry.key}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`border rounded-lg p-4 transition cursor-pointer ${
                    selectedKeys.has(entry.key)
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900 dark:bg-opacity-20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600'
                  }`}
                  onClick={() => toggleSelection(entry.key)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-4 flex-1">
                      {/* Checkbox */}
                      <input
                        type="checkbox"
                        checked={selectedKeys.has(entry.key)}
                        onChange={() => toggleSelection(entry.key)}
                        className="mt-1"
                        onClick={(e) => e.stopPropagation()}
                      />

                      {/* Info */}
                      <div className="flex-1">
                        <div className="font-mono text-sm text-gray-600 dark:text-gray-400 mb-2">
                          {entry.key.substring(0, 16)}...
                        </div>
                        
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                          <div>
                            <span className="text-gray-500 dark:text-gray-400">Size:</span>
                            <span className="ml-2 font-medium text-gray-900 dark:text-white">
                              {formatSize(entry.size_mb)}
                            </span>
                          </div>
                          
                          <div>
                            <span className="text-gray-500 dark:text-gray-400">Created:</span>
                            <span className="ml-2 font-medium text-gray-900 dark:text-white">
                              {formatDate(entry.created)}
                            </span>
                          </div>
                          
                          <div>
                            <span className="text-gray-500 dark:text-gray-400">Last Used:</span>
                            <span className="ml-2 font-medium text-gray-900 dark:text-white">
                              {formatDate(entry.last_accessed)}
                            </span>
                          </div>
                          
                          <div>
                            <span className="text-gray-500 dark:text-gray-400">Access Count:</span>
                            <span className="ml-2 font-medium text-gray-900 dark:text-white">
                              {entry.access_count}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}

