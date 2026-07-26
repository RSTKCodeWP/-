/**
 * Generation History Component
 * Displays and manages terrain generation history
 */

import { useState, useEffect } from 'react';
import { History, Trash2, RotateCcw, Download, X, Search, Clock, HardDrive } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { historyStorage } from '../utils/history-storage';
import type { GenerationHistoryItem } from '../types/history';
import { notify } from '../utils/toast';

/** Status values the history list can be filtered by. */
type HistoryFilter = 'all' | 'completed' | 'failed';

interface GenerationHistoryProps {
  onClose: () => void;
  onRepeat?: (item: GenerationHistoryItem) => void;
}

export default function GenerationHistory({ onClose, onRepeat }: GenerationHistoryProps) {
  const [history, setHistory] = useState<GenerationHistoryItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<HistoryFilter>('all');

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = () => {
    setHistory(historyStorage.getAll());
  };

  const handleDelete = (id: string) => {
    if (confirm('Delete this generation from history?')) {
      historyStorage.delete(id);
      loadHistory();
      notify.success('History item deleted');
    }
  };

  const handleClearAll = () => {
    if (confirm('Clear all generation history? This cannot be undone.')) {
      historyStorage.clearAll();
      loadHistory();
      notify.success('History cleared');
    }
  };

  const handleRepeat = (item: GenerationHistoryItem) => {
    if (onRepeat) {
      onRepeat(item);
      notify.success(`Repeating generation: ${item.name}`);
      onClose();
    }
  };

  const filteredHistory = history.filter(item => {
    const matchesSearch = 
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.config.exportFormats.some(fmt => fmt.toLowerCase().includes(searchQuery.toLowerCase()));
    
    const matchesStatus = filterStatus === 'all' || item.status === filterStatus;
    
    return matchesSearch && matchesStatus;
  });

  const stats = historyStorage.getStats();

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  const formatDuration = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    }
    return `${seconds}s`;
  };

  const formatFileSize = (bytes: number) => {
    const mb = bytes / (1024 * 1024);
    if (mb > 1000) {
      return `${(mb / 1024).toFixed(2)} GB`;
    }
    return `${mb.toFixed(2)} MB`;
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
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <History className="w-8 h-8" />
              <div>
                <h2 className="text-2xl font-bold">Generation History</h2>
                <p className="text-blue-100 text-sm">
                  {stats.total} generations • {stats.completed} completed • {stats.failed} failed
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={handleClearAll}
                className="flex items-center space-x-2 px-4 py-2 bg-red-500 hover:bg-red-600 rounded-lg transition"
              >
                <Trash2 className="w-4 h-4" />
                <span>Clear All</span>
              </button>
              <button
                onClick={onClose}
                className="p-2 hover:bg-white hover:bg-opacity-20 rounded-lg transition"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
          </div>

          {/* Search and Filter */}
          <div className="flex space-x-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search by name or format..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-lg bg-white bg-opacity-20 border border-white border-opacity-30 text-white placeholder-blue-100 focus:outline-none focus:ring-2 focus:ring-white"
              />
            </div>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value as HistoryFilter)}
              className="px-4 py-2 rounded-lg bg-white bg-opacity-20 border border-white border-opacity-30 text-white focus:outline-none focus:ring-2 focus:ring-white"
            >
              <option value="all" className="text-gray-900">All</option>
              <option value="completed" className="text-gray-900">Completed</option>
              <option value="failed" className="text-gray-900">Failed</option>
            </select>
          </div>
        </div>

        {/* History List */}
        <div className="p-6 overflow-y-auto" style={{ maxHeight: 'calc(90vh - 200px)' }}>
          {filteredHistory.length === 0 ? (
            <div className="text-center py-12">
              <History className="w-16 h-16 mx-auto text-gray-300 dark:text-gray-600 mb-4" />
              <p className="text-gray-500 dark:text-gray-400 text-lg">
                {searchQuery ? 'No matching history items' : 'No generation history yet'}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <AnimatePresence>
                {filteredHistory.map(item => (
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="bg-gray-50 dark:bg-gray-750 border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:shadow-md transition"
                  >
                    <div className="flex items-start justify-between gap-4">
                      {/* Thumbnail */}
                      {item.thumbnail && (
                        <div className="flex-shrink-0 w-32 h-24 rounded overflow-hidden bg-gray-200 dark:bg-gray-700">
                          <img
                            src={item.thumbnail}
                            alt={item.name}
                            className="w-full h-full object-cover"
                            onError={(e) => {
                              // Hide image if it fails to load
                              e.currentTarget.style.display = 'none';
                            }}
                          />
                        </div>
                      )}
                      
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-2">
                          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                            {item.name}
                          </h3>
                          <span
                            className={`px-2 py-1 text-xs rounded-full ${
                              item.status === 'completed'
                                ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                                : item.status === 'failed'
                                ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
                                : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300'
                            }`}
                          >
                            {item.status}
                          </span>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-gray-600 dark:text-gray-400">
                          <div className="flex items-center space-x-2">
                            <Clock className="w-4 h-4" />
                            <span>{formatDate(item.timestamp)}</span>
                          </div>
                          
                          {item.stats?.duration && (
                            <div className="flex items-center space-x-2">
                              <Clock className="w-4 h-4" />
                              <span>Duration: {formatDuration(item.stats.duration)}</span>
                            </div>
                          )}
                          
                          {item.stats?.fileSize && (
                            <div className="flex items-center space-x-2">
                              <HardDrive className="w-4 h-4" />
                              <span>{formatFileSize(item.stats.fileSize)}</span>
                            </div>
                          )}

                          <div>
                            <span className="font-medium">Resolution:</span> {item.config.resolution}px
                          </div>
                        </div>

                        <div className="mt-2 flex flex-wrap gap-1">
                          {item.config.exportFormats.map(format => (
                            <span
                              key={format}
                              className="px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-xs rounded-full"
                            >
                              {format.toUpperCase()}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="flex items-center space-x-2 ml-4">
                        {onRepeat && (
                          <button
                            onClick={() => handleRepeat(item)}
                            className="p-2 text-blue-600 hover:bg-blue-100 dark:hover:bg-blue-900 rounded-lg transition"
                            title="Repeat this generation"
                          >
                            <RotateCcw className="w-5 h-5" />
                          </button>
                        )}
                        
                        {item.downloadUrl && (
                          <a
                            href={item.downloadUrl}
                            download
                            className="p-2 text-green-600 hover:bg-green-100 dark:hover:bg-green-900 rounded-lg transition"
                            title="Download"
                          >
                            <Download className="w-5 h-5" />
                          </a>
                        )}
                        
                        <button
                          onClick={() => handleDelete(item.id)}
                          className="p-2 text-red-600 hover:bg-red-100 dark:hover:bg-red-900 rounded-lg transition"
                          title="Delete"
                        >
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}

