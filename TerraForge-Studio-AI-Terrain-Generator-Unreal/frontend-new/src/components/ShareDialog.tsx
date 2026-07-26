/**
 * Share Dialog Component
 * UI for creating and managing share links
 */

import { useState } from 'react';
import { Share2, Copy, Link, Clock, Users, X, Check, Calendar } from 'lucide-react';
import { motion } from 'framer-motion';
import { notify } from '../utils/toast';
import { shareManager } from '../utils/share-manager';
import type { ShareConfig, ShareOptions } from '../types/share';

interface ShareDialogProps {
  config: ShareConfig;
  onClose: () => void;
}

export default function ShareDialog({ config, onClose }: ShareDialogProps) {
  const [shareUrl, setShareUrl] = useState<string>('');
  const [_shortId, setShortId] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  
  // Options
  const [expiresIn, setExpiresIn] = useState<string>('7d');
  const [maxAccess, setMaxAccess] = useState<number | undefined>(undefined);
  const [title, setTitle] = useState(config.name);
  const [description, setDescription] = useState('');

  const handleGenerateLink = async () => {
    setIsGenerating(true);
    
    try {
      const options: ShareOptions = {
        expiresIn: parseExpiry(expiresIn),
        maxAccess: maxAccess || undefined,
      };

      const result = await shareManager.create(
        {
          ...config,
          name: title || config.name,
        },
        options
      );

      setShareUrl(result.url);
      setShortId(result.shareLink.shortId);
      notify.success('Share link created!');
    } catch (error) {
      console.error('Failed to create share link:', error);
      notify.error('Failed to create share link');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopy = async () => {
    const success = await shareManager.copyToClipboard(shareUrl);
    if (success) {
      setIsCopied(true);
      notify.success('Link copied to clipboard!');
      setTimeout(() => setIsCopied(false), 2000);
    } else {
      notify.error('Failed to copy link');
    }
  };

  const parseExpiry = (value: string): number | undefined => {
    const map: Record<string, number> = {
      '1h': 60 * 60 * 1000,
      '24h': 24 * 60 * 60 * 1000,
      '7d': 7 * 24 * 60 * 60 * 1000,
      '30d': 30 * 24 * 60 * 60 * 1000,
      'never': 0,
    };
    return map[value] || undefined;
  };

  const formatExpiry = (value: string): string => {
    const map: Record<string, string> = {
      '1h': '1 hour',
      '24h': '24 hours',
      '7d': '7 days',
      '30d': '30 days',
      'never': 'Never',
    };
    return map[value] || value;
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-2xl w-full overflow-hidden"
      >
        {/* Header */}
        <div className="bg-gradient-to-r from-green-600 to-teal-600 text-white p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Share2 className="w-8 h-8" />
              <div>
                <h2 className="text-2xl font-bold">Share Project</h2>
                <p className="text-green-100 text-sm">Create a shareable link</p>
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

        <div className="p-6 space-y-6">
          {/* Project Info */}
          <div className="bg-gray-50 dark:bg-gray-750 rounded-lg p-4">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-2">Project Details</h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-gray-500 dark:text-gray-400">Area:</span>
                <span className="ml-2 text-gray-900 dark:text-white">{config.name}</span>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400">Resolution:</span>
                <span className="ml-2 text-gray-900 dark:text-white">{config.resolution}px</span>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400">Formats:</span>
                <span className="ml-2 text-gray-900 dark:text-white">
                  {config.exportFormats.join(', ').toUpperCase()}
                </span>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400">Source:</span>
                <span className="ml-2 text-gray-900 dark:text-white capitalize">
                  {config.elevationSource}
                </span>
              </div>
            </div>
          </div>

          {!shareUrl ? (
            <>
              {/* Custom Title */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Share Title (Optional)
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder={config.name}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:ring-2 focus:ring-green-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Description (Optional)
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Add a description for people who receive this link..."
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:ring-2 focus:ring-green-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
              </div>

              {/* Expiry */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center">
                  <Clock className="w-4 h-4 mr-2" />
                  Link Expiration
                </label>
                <select
                  value={expiresIn}
                  onChange={(e) => setExpiresIn(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:ring-2 focus:ring-green-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                >
                  <option value="1h">1 hour</option>
                  <option value="24h">24 hours</option>
                  <option value="7d">7 days</option>
                  <option value="30d">30 days</option>
                  <option value="never">Never expire</option>
                </select>
              </div>

              {/* Max Access */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center">
                  <Users className="w-4 h-4 mr-2" />
                  Maximum Access Count (Optional)
                </label>
                <input
                  type="number"
                  value={maxAccess || ''}
                  onChange={(e) => setMaxAccess(e.target.value ? parseInt(e.target.value) : undefined)}
                  placeholder="Unlimited"
                  min="1"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:ring-2 focus:ring-green-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Leave empty for unlimited access
                </p>
              </div>

              {/* Generate Button */}
              <button
                onClick={handleGenerateLink}
                disabled={isGenerating}
                className="w-full flex items-center justify-center space-x-2 bg-green-600 text-white px-4 py-3 rounded-md hover:bg-green-700 disabled:bg-gray-400 transition"
              >
                {isGenerating ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Generating...</span>
                  </>
                ) : (
                  <>
                    <Link className="w-5 h-5" />
                    <span>Generate Share Link</span>
                  </>
                )}
              </button>
            </>
          ) : (
            <>
              {/* Generated Link */}
              <div className="bg-green-50 dark:bg-green-900 dark:bg-opacity-20 border border-green-200 dark:border-green-700 rounded-lg p-4">
                <div className="flex items-center space-x-2 mb-3">
                  <Check className="w-5 h-5 text-green-600 dark:text-green-400" />
                  <span className="font-semibold text-green-900 dark:text-green-100">
                    Share Link Created!
                  </span>
                </div>
                
                <div className="flex items-center space-x-2 bg-white dark:bg-gray-800 rounded-md p-3">
                  <input
                    type="text"
                    value={shareUrl}
                    readOnly
                    className="flex-1 bg-transparent border-none focus:outline-none text-sm text-gray-900 dark:text-white"
                  />
                  <button
                    onClick={handleCopy}
                    className={`flex items-center space-x-2 px-3 py-2 rounded-md transition ${
                      isCopied
                        ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                        : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300 hover:bg-gray-200'
                    }`}
                  >
                    {isCopied ? (
                      <>
                        <Check className="w-4 h-4" />
                        <span className="text-sm">Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-4 h-4" />
                        <span className="text-sm">Copy</span>
                      </>
                    )}
                  </button>
                </div>

                <div className="mt-3 text-sm text-gray-600 dark:text-gray-400 space-y-1">
                  <div className="flex items-center space-x-2">
                    <Calendar className="w-4 h-4" />
                    <span>Expires: {formatExpiry(expiresIn)}</span>
                  </div>
                  {maxAccess && (
                    <div className="flex items-center space-x-2">
                      <Users className="w-4 h-4" />
                      <span>Max access: {maxAccess} times</span>
                    </div>
                  )}
                </div>
              </div>

              {/* New Link Button */}
              <button
                onClick={() => {
                  setShareUrl('');
                  setShortId('');
                }}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-md hover:bg-gray-50 dark:hover:bg-gray-700 transition"
              >
                Create Another Link
              </button>
            </>
          )}
        </div>
      </motion.div>
    </div>
  );
}

