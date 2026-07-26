/**
 * Mobile Navigation Component
 * Bottom navigation bar for mobile devices
 */

import { Map, Box, History, Settings, Share2 } from 'lucide-react';

interface MobileNavProps {
  activeTab: '2d' | '3d';
  onTabChange: (tab: '2d' | '3d') => void;
  onHistoryOpen: () => void;
  onShareOpen: () => void;
  onSettingsOpen: () => void;
}

export default function MobileNav({
  activeTab,
  onTabChange,
  onHistoryOpen,
  onShareOpen,
  onSettingsOpen,
}: MobileNavProps) {
  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 z-40 safe-area-bottom">
      <div className="grid grid-cols-5 gap-1 p-2">
        {/* 2D Map */}
        <button
          onClick={() => onTabChange('2d')}
          className={`flex flex-col items-center justify-center py-2 px-1 rounded-lg transition ${
            activeTab === '2d'
              ? 'bg-blue-600 text-white'
              : 'text-gray-600 dark:text-gray-400'
          }`}
        >
          <Map className="w-5 h-5 mb-1" />
          <span className="text-xs font-medium">Map</span>
        </button>

        {/* 3D Preview */}
        <button
          onClick={() => onTabChange('3d')}
          className={`flex flex-col items-center justify-center py-2 px-1 rounded-lg transition ${
            activeTab === '3d'
              ? 'bg-blue-600 text-white'
              : 'text-gray-600 dark:text-gray-400'
          }`}
        >
          <Box className="w-5 h-5 mb-1" />
          <span className="text-xs font-medium">3D</span>
        </button>

        {/* History */}
        <button
          onClick={onHistoryOpen}
          className="flex flex-col items-center justify-center py-2 px-1 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition"
        >
          <History className="w-5 h-5 mb-1" />
          <span className="text-xs font-medium">History</span>
        </button>

        {/* Share */}
        <button
          onClick={onShareOpen}
          className="flex flex-col items-center justify-center py-2 px-1 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition"
        >
          <Share2 className="w-5 h-5 mb-1" />
          <span className="text-xs font-medium">Share</span>
        </button>

        {/* Settings */}
        <button
          onClick={onSettingsOpen}
          className="flex flex-col items-center justify-center py-2 px-1 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition"
        >
          <Settings className="w-5 h-5 mb-1" />
          <span className="text-xs font-medium">Settings</span>
        </button>
      </div>
    </nav>
  );
}

