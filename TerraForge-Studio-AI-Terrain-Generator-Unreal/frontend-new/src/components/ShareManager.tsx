/**
 * Share Manager Component
 * Manage all created share links
 */

import { useState, useEffect } from 'react';
import { Share2, Trash2, X, Copy, Eye, EyeOff, ExternalLink } from 'lucide-react';
import { motion } from 'framer-motion';
import { shareManager } from '../utils/share-manager';
import { notify } from '../utils/toast';
import type { ShareLink } from '../types/share';

interface ShareManagerProps {
  onClose: () => void;
}

export default function ShareManager({ onClose }: ShareManagerProps) {
  const [links, setLinks] = useState<ShareLink[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadLinks();
  }, []);

  const loadLinks = async () => {
    setLoading(true);
    try {
      const result = await shareManager.list();
      setLinks(result);
    } catch (error) {
      console.error('Failed to load share links:', error);
      notify.error('Failed to load share links');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async (shortId: string) => {
    const url = shareManager.generateUrl(shortId);
    const success = await shareManager.copyToClipboard(url);
    if (success) {
      notify.success('Link copied!');
    }
  };

  const handleDeactivate = async (shortId: string) => {
    try {
      await shareManager.deactivate(shortId);
      notify.success('Link deactivated');
      loadLinks();
    } catch (error) {
      notify.error('Failed to deactivate link');
    }
  };

  const handleDelete = async (shortId: string) => {
    if (!confirm('Delete this share link?')) return;

    try {
      await shareManager.delete(shortId);
      notify.success('Link deleted');
      loadLinks();
    } catch (error) {
      notify.error('Failed to delete link');
    }
  };

  const formatDate = (isoString: string) => {
    return new Date(isoString).toLocaleDateString() + ' ' + new Date(isoString).toLocaleTimeString();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden"
      >
        {/* Header */}
        <div className="bg-gradient-to-r from-green-600 to-teal-600 text-white p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Share2 className="w-8 h-8" />
              <div>
                <h2 className="text-2xl font-bold">Share Links</h2>
                <p className="text-green-100 text-sm">Manage your shared projects</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white hover:bg-opacity-20 rounded-lg transition"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto" style={{ maxHeight: 'calc(90vh - 120px)' }}>
          {loading ? (
            <div className="text-center py-12">
              <div className="w-12 h-12 border-4 border-green-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-gray-500 dark:text-gray-400">Loading share links...</p>
            </div>
          ) : links.length === 0 ? (
            <div className="text-center py-12">
              <Share2 className="w-16 h-16 mx-auto text-gray-300 dark:text-gray-600 mb-4" />
              <p className="text-gray-500 dark:text-gray-400 text-lg">No share links yet</p>
              <p className="text-sm text-gray-400 dark:text-gray-500 mt-2">
                Create a share link from the Export panel
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {links.map((link) => (
                <motion.div
                  key={link.shortId}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`border rounded-lg p-4 ${
                    link.isActive
                      ? 'border-gray-200 dark:border-gray-700'
                      : 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900 dark:bg-opacity-10'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                          {link.config.name || link.metadata?.title || 'Untitled'}
                        </h3>
                        {link.isActive ? (
                          <span className="flex items-center space-x-1 px-2 py-1 bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 text-xs rounded-full">
                            <Eye className="w-3 h-3" />
                            <span>Active</span>
                          </span>
                        ) : (
                          <span className="flex items-center space-x-1 px-2 py-1 bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300 text-xs rounded-full">
                            <EyeOff className="w-3 h-3" />
                            <span>Inactive</span>
                          </span>
                        )}
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm text-gray-600 dark:text-gray-400">
                        <div>
                          <span className="font-medium">Created:</span>
                          <p className="text-gray-900 dark:text-white">{formatDate(link.createdAt.toString())}</p>
                        </div>
                        
                        <div>
                          <span className="font-medium">Access Count:</span>
                          <p className="text-gray-900 dark:text-white">
                            {link.accessCount} {link.maxAccess ? `/ ${link.maxAccess}` : ''}
                          </p>
                        </div>

                        {link.expiresAt && (
                          <div>
                            <span className="font-medium">Expires:</span>
                            <p className="text-gray-900 dark:text-white">{formatDate(link.expiresAt.toString())}</p>
                          </div>
                        )}

                        <div>
                          <span className="font-medium">Short ID:</span>
                          <p className="text-gray-900 dark:text-white font-mono">{link.shortId}</p>
                        </div>
                      </div>

                      {link.metadata?.description && (
                        <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                          {link.metadata.description}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center space-x-2 ml-4">
                      <button
                        onClick={() => handleCopy(link.shortId)}
                        className="p-2 text-blue-600 hover:bg-blue-100 dark:hover:bg-blue-900 rounded-lg transition"
                        title="Copy link"
                      >
                        <Copy className="w-5 h-5" />
                      </button>

                      {link.isActive && (
                        <button
                          onClick={() => handleDeactivate(link.shortId)}
                          className="p-2 text-orange-600 hover:bg-orange-100 dark:hover:bg-orange-900 rounded-lg transition"
                          title="Deactivate"
                        >
                          <EyeOff className="w-5 h-5" />
                        </button>
                      )}

                      <button
                        onClick={() => handleDelete(link.shortId)}
                        className="p-2 text-red-600 hover:bg-red-100 dark:hover:bg-red-900 rounded-lg transition"
                        title="Delete"
                      >
                        <Trash2 className="w-5 h-5" />
                      </button>

                      <a
                        href={shareManager.generateUrl(link.shortId)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-2 text-green-600 hover:bg-green-100 dark:hover:bg-green-900 rounded-lg transition"
                        title="Open link"
                      >
                        <ExternalLink className="w-5 h-5" />
                      </a>
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

