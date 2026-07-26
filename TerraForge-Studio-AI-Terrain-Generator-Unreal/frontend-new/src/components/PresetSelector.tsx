/**
 * Preset Selector Component
 * Allows users to select from predefined terrain generation presets
 */

import { useState } from 'react';
import { Star, Sparkles, Search, X } from 'lucide-react';
import { BUILT_IN_PRESETS, type TerrainPreset } from '../types/presets';
import { motion, AnimatePresence } from 'framer-motion';

interface PresetSelectorProps {
  onSelectPreset: (preset: TerrainPreset) => void;
  onClose: () => void;
}

export default function PresetSelector({ onSelectPreset, onClose }: PresetSelectorProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const categories = [
    { id: 'all', name: 'All Presets', icon: '✨' },
    { id: 'gaming', name: 'Gaming', icon: '🎮' },
    { id: 'professional', name: 'Professional', icon: '💼' },
    { id: 'planning', name: 'Planning', icon: '📐' },
    { id: 'general', name: 'General', icon: '🌍' },
  ];

  const filteredPresets = BUILT_IN_PRESETS.filter(preset => {
    const matchesSearch = 
      preset.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      preset.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      preset.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));
    
    const matchesCategory = selectedCategory === 'all' || preset.category === selectedCategory;
    
    return matchesSearch && matchesCategory;
  });

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-5xl w-full max-h-[90vh] overflow-hidden"
      >
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <Sparkles className="w-8 h-8" />
              <div>
                <h2 className="text-2xl font-bold">Terrain Presets</h2>
                <p className="text-blue-100 text-sm">Choose a template to get started quickly</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white hover:bg-opacity-20 rounded-lg transition"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search presets by name, description, or tags..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-3 rounded-lg bg-white bg-opacity-20 border border-white border-opacity-30 text-white placeholder-blue-100 focus:outline-none focus:ring-2 focus:ring-white"
            />
          </div>
        </div>

        {/* Categories */}
        <div className="border-b border-gray-200 dark:border-gray-700 px-6 py-4">
          <div className="flex space-x-2 overflow-x-auto">
            {categories.map(category => (
              <button
                key={category.id}
                onClick={() => setSelectedCategory(category.id)}
                className={`
                  flex items-center space-x-2 px-4 py-2 rounded-lg whitespace-nowrap transition
                  ${selectedCategory === category.id
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                  }
                `}
              >
                <span>{category.icon}</span>
                <span className="font-medium">{category.name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Presets Grid */}
        <div className="p-6 overflow-y-auto" style={{ maxHeight: 'calc(90vh - 250px)' }}>
          {filteredPresets.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-500 dark:text-gray-400 text-lg">
                No presets found matching your criteria
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <AnimatePresence>
                {filteredPresets.map(preset => (
                  <motion.div
                    key={preset.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="bg-white dark:bg-gray-750 border border-gray-200 dark:border-gray-700 rounded-lg p-5 cursor-pointer hover:shadow-lg transition group"
                    onClick={() => onSelectPreset(preset)}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="text-4xl">{preset.icon}</div>
                      <Star className="w-5 h-5 text-gray-300 group-hover:text-yellow-500 transition" />
                    </div>
                    
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                      {preset.name}
                    </h3>
                    
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                      {preset.description}
                    </p>
                    
                    <div className="flex flex-wrap gap-1 mb-3">
                      {preset.tags.slice(0, 3).map(tag => (
                        <span
                          key={tag}
                          className="px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-xs rounded-full"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                    
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      <div>Resolution: {preset.config.resolution}px</div>
                      <div>Formats: {preset.config.exportFormats.join(', ').toUpperCase()}</div>
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

