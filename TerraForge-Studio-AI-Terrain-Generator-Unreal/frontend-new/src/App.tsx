/**
 * TerraForge Studio - Main Application
 */

import { useState, useEffect, useRef } from 'react';
import { Globe, Settings as SettingsIcon, Download, Map, Box, History, Database, Share2, ListChecks, Plug } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import KeyboardShortcuts from './components/KeyboardShortcuts';
import MapSelector from './components/MapSelector';
import ExportPanel from './components/ExportPanel';
import AIAssistant from './components/AIAssistant';
import StatusMonitor from './components/StatusMonitor';
import Preview3D from './components/Preview3D';
import SettingsPage from './components/Settings/SettingsPage';
import SetupWizard from './components/SetupWizard';
import ThemeToggle from './components/ThemeToggle';
import GenerationHistory from './components/GenerationHistory';
import CacheManager from './components/CacheManager';
import ShareDialog from './components/ShareDialog';
import ShareManager from './components/ShareManager';
import MobileNav from './components/MobileNav';
import QueueManager from './components/QueueManager';
import BatchProcessor from './components/BatchProcessor';
import PluginMarketplace from './components/PluginMarketplace';
import { api, terraforgeApi } from './services/api';
import { settingsApi } from './services/settings-api';
import { notify } from './utils/toast';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { useWebSocket } from './hooks/useWebSocket';
import { useIsMobile } from './hooks/useMediaQuery';
import { historyStorage } from './utils/history-storage';
import type {
  BoundingBox,
  ExportFormat,
  ElevationSource,
  GenerationStatus,
  HealthStatus,
} from './types';
import type { GenerationHistoryItem } from './types/history';

function App() {
  const { t } = useTranslation();
  
  // Восстановить bbox из localStorage
  const [selectedBbox, setSelectedBbox] = useState<BoundingBox | null>(() => {
    try {
      const saved = localStorage.getItem('terraforge_selected_bbox');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [activeTab, setActiveTab] = useState<'2d' | '3d'>('2d');
  const [currentTask, setCurrentTask] = useState<GenerationStatus | null>(null);
  const [appHealth, setAppHealth] = useState<HealthStatus | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showWizard, setShowWizard] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showCache, setShowCache] = useState(false);
  const [showShare, setShowShare] = useState(false);
  const [showShareManager, setShowShareManager] = useState(false);
  const [showQueue, setShowQueue] = useState(false);
  const [showBatch, setShowBatch] = useState(false);
  const [showPlugins, setShowPlugins] = useState(false);
  const [aiEnabled, setAiEnabled] = useState(false);
  const [wsUrl, setWsUrl] = useState<string | null>(null);
  const generationStartTime = useRef<number>(0);
  
  // Mobile detection
  const isMobile = useIsMobile();

  // WebSocket connection for live updates
  useWebSocket(wsUrl, {
    onMessage: (message) => {
      if (message.type !== 'status_update') return;

      // The server sends the full GenerationStatus payload alongside `type`,
      // which is envelope-only and dropped here. `warnings` is defaulted so a
      // server predating that field still yields a well-formed task.
      const { type: _type, ...rest } = message;
      const incoming = rest as unknown as GenerationStatus;
      const task: GenerationStatus = { ...incoming, warnings: incoming.warnings ?? [] };

      setCurrentTask(task);

      if (task.status === 'completed') {
        notify.success('Terrain generation completed!');
        saveToHistory(task, 'completed', task.result?.thumbnail_base64 ?? undefined);
      } else if (task.status === 'failed') {
        notify.error('Terrain generation failed');
        saveToHistory(task, 'failed');
      }
    },
    onOpen: () => {
      notify.info('Connected to live updates');
    },
    onClose: () => {
      // Reconnection is handled by the hook; nothing to do here.
    },
    reconnect: true,
  });

  // Сохранить bbox в localStorage при изменении
  useEffect(() => {
    if (selectedBbox) {
      localStorage.setItem('terraforge_selected_bbox', JSON.stringify(selectedBbox));
    } else {
      localStorage.removeItem('terraforge_selected_bbox');
    }
  }, [selectedBbox]);

  // Check API health, first run, and AI settings on startup
  useEffect(() => {
    Promise.all([
      terraforgeApi.getHealth(),
      settingsApi.checkFirstRun(),
      settingsApi.getSettings()
    ]).then(([health, firstRun, settings]) => {
      setAppHealth(health);
      setShowWizard(firstRun.show_wizard);
      setAiEnabled(settings?.ai?.enabled || false);
    }).catch(console.error);
  }, []);

  // Helper function to save generation to history
  const saveToHistory = (
    data: GenerationStatus,
    status: 'completed' | 'failed',
    thumbnail?: string,
  ) => {
    if (!selectedBbox || !currentTask) return;

    const duration = Date.now() - generationStartTime.current;
    const historyItem: GenerationHistoryItem = {
      id: data.task_id,
      timestamp: Date.now(),
      name: currentTask.current_step || 'terrain',
      bbox: selectedBbox,
      config: {
        resolution: 2048, // These should come from the actual config
        exportFormats: [],
        elevationSource: 'auto',
        enableRoads: true,
        enableBuildings: true,
        enableWeightmaps: true,
      },
      status,
      downloadUrl: data.download_url ?? undefined,
      thumbnail: thumbnail,
      stats: {
        duration,
      },
    };
    historyStorage.add(historyItem);
  };

  // Keyboard shortcuts
  useKeyboardShortcuts({
    'ctrl+g': () => {
      // Trigger generation if export panel is visible
      if (selectedBbox) {
        notify.info('Press Generate button to start (Ctrl+G shortcut active)');
      } else {
        notify.error('Please select an area on the map first');
      }
    },
    'ctrl+d': () => {
      // Toggle theme (will be implemented when we import useTheme)
      const event = new CustomEvent('toggle-theme');
      window.dispatchEvent(event);
      notify.info('Theme toggled');
    },
    'ctrl+3': () => {
      // Toggle to 3D view
      setActiveTab('3d');
      notify.info('Switched to 3D Preview');
    },
    'ctrl+2': () => {
      // Toggle to 2D view
      setActiveTab('2d');
      notify.info('Switched to 2D Map');
    },
    'ctrl+s': () => {
      // Open settings
      setShowSettings(true);
    },
    'ctrl+h': () => {
      // Open history
      setShowHistory(true);
    },
    'ctrl+shift+c': () => {
      // Open cache manager
      setShowCache(true);
    },
    'ctrl+shift+s': () => {
      // Open share manager
      setShowShareManager(true);
    },
    'escape': () => {
      // Close modals
      if (showSettings) setShowSettings(false);
      if (showWizard) setShowWizard(false);
      if (showHistory) setShowHistory(false);
      if (showCache) setShowCache(false);
      if (showShare) setShowShare(false);
      if (showShareManager) setShowShareManager(false);
      if (showQueue) setShowQueue(false);
      if (showBatch) setShowBatch(false);
      if (showPlugins) setShowPlugins(false);
    },
  });

  const handleGenerateTerrain = async (config: {
    name: string;
    resolution: number;
    exportFormats: ExportFormat[];
    elevationSource: ElevationSource;
    enableRoads: boolean;
    enableBuildings: boolean;
    enableWeightmaps: boolean;
  }) => {
    if (!selectedBbox) {
      notify.error('Please select an area on the map first');
      return;
    }

    const loadingToast = notify.loading('Starting terrain generation...');
    generationStartTime.current = Date.now();

    try {
      const status = await terraforgeApi.generateTerrain({
        bbox: selectedBbox,
        name: config.name,
        resolution: config.resolution,
        export_formats: config.exportFormats,
        elevation_source: config.elevationSource,
        enable_roads: config.enableRoads,
        enable_buildings: config.enableBuildings,
        enable_weightmaps: config.enableWeightmaps,
        enable_vegetation: true,
        enable_water_bodies: true,
      });

      setCurrentTask(status);
      notify.dismiss(loadingToast);
      notify.success(`Generation started: ${config.name}`);

      // Connect to WebSocket for real-time updates
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsBaseUrl = `${protocol}//${window.location.hostname}:8000`;
      setWsUrl(`${wsBaseUrl}/ws/generation/${status.task_id}`);

    } catch (error) {
      console.error('Generation failed:', error);
      notify.dismiss(loadingToast);
      notify.error('Failed to start terrain generation');
    }
  };

  const handleSubmitBatch = async (jobs: Array<{
    name: string;
    bbox: BoundingBox | null;
    resolution: number;
    exportFormats: ExportFormat[];
    elevationSource: ElevationSource;
  }>) => {
    const ready = jobs.filter((job) => job.bbox !== null);
    if (ready.length === 0) {
      notify.error('Each batch job needs an area selected');
      return;
    }

    try {
      await api.post('/api/batch/add', {
        jobs: ready.map((job) => ({
          name: job.name,
          bbox: job.bbox,
          resolution: job.resolution,
          export_formats: job.exportFormats,
          elevation_source: job.elevationSource,
        })),
        priority: 0,
      });

      notify.success(`Queued ${ready.length} job(s)`);
      setShowBatch(false);
      setShowQueue(true);
    } catch {
      notify.error('Could not queue batch jobs');
    }
  };

  const handleRepeatGeneration = (item: GenerationHistoryItem) => {
    setSelectedBbox(item.bbox);
    handleGenerateTerrain({
      name: item.name + '_repeat',
      resolution: item.config.resolution,
      exportFormats: item.config.exportFormats,
      elevationSource: item.config.elevationSource,
      enableRoads: item.config.enableRoads,
      enableBuildings: item.config.enableBuildings,
      enableWeightmaps: item.config.enableWeightmaps,
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 transition-colors duration-200">
      {/* Setup Wizard */}
      {showWizard && (
        <SetupWizard onComplete={() => setShowWizard(false)} />
      )}

      {/* Settings Modal */}
      {showSettings && (
        <SettingsPage onClose={() => setShowSettings(false)} />
      )}

      {/* History Modal */}
      {showHistory && (
        <GenerationHistory
          onClose={() => setShowHistory(false)}
          onRepeat={handleRepeatGeneration}
        />
      )}

      {/* Cache Manager Modal */}
      {showCache && (
        <CacheManager
          onClose={() => setShowCache(false)}
        />
      )}

      {/* Share Dialog */}
      {showShare && selectedBbox && (
        <ShareDialog
          config={{
            bbox: selectedBbox,
            name: 'Shared Terrain',
            resolution: 2048,
            exportFormats: ['gltf'],
            elevationSource: 'auto',
            enableRoads: true,
            enableBuildings: true,
            enableWeightmaps: true,
          }}
          onClose={() => setShowShare(false)}
        />
      )}

      {/* Share Manager */}
      {showShareManager && (
        <ShareManager
          onClose={() => setShowShareManager(false)}
        />
      )}

      {/* Batch queue */}
      {showQueue && <QueueManager onClose={() => setShowQueue(false)} />}

      {/* Plugins */}
      {showPlugins && <PluginMarketplace onClose={() => setShowPlugins(false)} />}

      {/* Batch job builder */}
      {showBatch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-lg bg-white shadow-xl dark:bg-gray-900">
            <div className="flex items-center justify-between border-b border-gray-200 p-4 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Batch Generation
              </h2>
              <button
                onClick={() => setShowBatch(false)}
                aria-label="Close"
                className="rounded-md p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                &times;
              </button>
            </div>
            <BatchProcessor onSubmitBatch={handleSubmitBatch} />
          </div>
        </div>
      )}

      {/* Header */}
      <header className="glass border-b border-gray-200 dark:border-gray-700">
        <div className={`container mx-auto px-4 ${isMobile ? 'py-2' : 'py-4'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Globe className={`${isMobile ? 'w-6 h-6' : 'w-8 h-8'} text-blue-600 dark:text-blue-400`} />
              <div>
                <h1 className={`${isMobile ? 'text-lg' : 'text-2xl'} font-bold text-gray-900 dark:text-white`}>
                  {t('app.title')}
                </h1>
                {!isMobile && (
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {t('app.subtitle')} {appHealth?.version && `v${appHealth.version}`}
                  </p>
                )}
              </div>
            </div>

            <div className={`flex items-center ${isMobile ? 'space-x-2' : 'space-x-4'}`}>
              {!isMobile && (
                <>
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    {appHealth?.data_sources && (
                      <span>
                        {appHealth.data_sources.available.length} / {appHealth.data_sources.total} sources
                      </span>
                    )}
                  </div>
                  
                  <ThemeToggle />
                  
                  <button
                    onClick={() => setShowShareManager(true)}
                    className="flex items-center space-x-2 px-4 py-2 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-900 dark:text-white rounded-md border border-gray-300 dark:border-gray-600 transition"
                    title="Share Manager (Ctrl+Shift+S)"
                  >
                    <Share2 className="w-5 h-5" />
                    <span className="hidden xl:inline">{t('nav.share')}</span>
                  </button>

                  <button
                    onClick={() => setShowCache(true)}
                    className="flex items-center space-x-2 px-4 py-2 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-900 dark:text-white rounded-md border border-gray-300 dark:border-gray-600 transition"
                    title="Cache Manager (Ctrl+Shift+C)"
                  >
                    <Database className="w-5 h-5" />
                    <span className="hidden xl:inline">{t('nav.cache')}</span>
                  </button>

                  <button
                    onClick={() => setShowQueue(true)}
                    className="flex items-center space-x-2 px-4 py-2 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-900 dark:text-white rounded-md border border-gray-300 dark:border-gray-600 transition"
                    title="Batch queue"
                  >
                    <ListChecks className="w-5 h-5" />
                    <span className="hidden xl:inline">Queue</span>
                  </button>

                  <button
                    onClick={() => setShowPlugins(true)}
                    className="flex items-center space-x-2 px-4 py-2 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-900 dark:text-white rounded-md border border-gray-300 dark:border-gray-600 transition"
                    title="Plugins"
                  >
                    <Plug className="w-5 h-5" />
                    <span className="hidden xl:inline">Plugins</span>
                  </button>

                  <button
                    onClick={() => setShowHistory(true)}
                    className="flex items-center space-x-2 px-4 py-2 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-900 dark:text-white rounded-md border border-gray-300 dark:border-gray-600 transition"
                    title="Generation History (Ctrl+H)"
                  >
                    <History className="w-5 h-5" />
                    <span className="hidden lg:inline">{t('nav.history')}</span>
                  </button>
                  
                  <button
                    onClick={() => setShowSettings(true)}
                    className="flex items-center space-x-2 px-4 py-2 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-900 dark:text-white rounded-md border border-gray-300 dark:border-gray-600 transition"
                    title="Settings (Ctrl+S)"
                  >
                    <SettingsIcon className="w-5 h-5" />
                    <span className="hidden lg:inline">{t('nav.settings')}</span>
                  </button>
                </>
              )}
              
              {isMobile && (
                <ThemeToggle />
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className={`container mx-auto px-4 ${isMobile ? 'py-3 pb-20' : 'py-6'}`}>
        <div className={`grid grid-cols-1 ${isMobile ? 'gap-3' : 'lg:grid-cols-3 gap-6'}`}>
          {/* Left Panel - Map & 3D Preview */}
          <div className={`${isMobile ? '' : 'lg:col-span-2'} space-y-${isMobile ? '3' : '6'}`}>
            {/* Tab Switcher - Hide on mobile (use bottom nav instead) */}
            {!isMobile && (
              <div className="glass rounded-lg p-2 flex space-x-2">
              <button
                onClick={() => setActiveTab('2d')}
                className={`flex-1 flex items-center justify-center space-x-2 px-4 py-2 rounded-md transition ${
                  activeTab === '2d'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                <Map className="w-5 h-5" />
                <span>2D Map Selector</span>
              </button>
              <button
                onClick={() => setActiveTab('3d')}
                className={`flex-1 flex items-center justify-center space-x-2 px-4 py-2 rounded-md transition ${
                  activeTab === '3d'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                <Box className="w-5 h-5" />
                <span>3D Preview</span>
              </button>
            </div>
            )}

            {/* Map or 3D View */}
            <div className="glass rounded-lg overflow-hidden shadow-lg" style={{ height: isMobile ? '400px' : '600px' }}>
              {activeTab === '2d' ? (
                <MapSelector
                  selectedBbox={selectedBbox}
                  onBboxChange={setSelectedBbox}
                />
              ) : (
                <Preview3D bbox={selectedBbox} />
              )}
            </div>
          </div>

          {/* Right Panel - Controls & Status */}
          <div className={`space-y-${isMobile ? '3' : '6'}`}>
            {/* Export Configuration */}
            <div className="glass rounded-lg p-6 shadow-lg">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center">
                <Download className="w-5 h-5 mr-2" />
                {t('export.title')}
              </h2>
              <ExportPanel
                onGenerate={handleGenerateTerrain}
                disabled={!selectedBbox}
                aiEnabled={aiEnabled}
              />
            </div>

            {/* AI Assistant - только если включен в настройках */}
            {aiEnabled && (
              <div className="glass rounded-lg p-6 shadow-lg">
                <AIAssistant
                  bbox={selectedBbox}
                  onApplyRecommendations={(_settings) => {
                    // Apply AI recommendations to export config
                    notify.success('AI recommendations applied');
                  }}
                />
              </div>
            )}

            {/* Generation Status */}
            {currentTask && (
              <div className="glass rounded-lg p-6 shadow-lg">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center">
                  <Download className="w-5 h-5 mr-2" />
                  Generation Status
                </h2>
                <StatusMonitor status={currentTask} />
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Mobile Bottom Navigation */}
      {isMobile && (
        <MobileNav
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onHistoryOpen={() => setShowHistory(true)}
          onShareOpen={() => setShowShareManager(true)}
          onSettingsOpen={() => setShowSettings(true)}
        />
      )}

      {/* Footer - Hide on mobile */}
      {!isMobile && (
        <footer className="mt-12 py-6 text-center text-sm text-gray-600 dark:text-gray-400">
          <p>
            TerraForge Studio - Professional Cross-Platform 3D Terrain Generator
          </p>
          <p className="mt-1">
            Supports Unreal Engine 5, Unity, GLTF, and GeoTIFF
          </p>
        </footer>
      )}

      {/* Keyboard Shortcuts Helper */}
      <KeyboardShortcuts />
    </div>
  );
}

export default App;

