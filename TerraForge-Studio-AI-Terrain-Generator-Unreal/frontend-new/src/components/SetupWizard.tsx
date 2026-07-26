/**
 * Setup Wizard - First-time setup assistant
 */

import { useState } from 'react';
import { Rocket, Globe, Key, Check } from 'lucide-react';
import { settingsApi } from '@/services/settings-api';
import type { SettingsUpdate } from '@/types/settings';

interface SetupWizardProps {
  onComplete: () => void;
}

const SetupWizard: React.FC<SetupWizardProps> = ({ onComplete }) => {
  const [step, setStep] = useState(1);
  const [language, setLanguage] = useState<'en' | 'ru'>('en');
  const [defaultEngine, setDefaultEngine] = useState<'unreal5' | 'unity' | 'generic'>('unreal5');
  const [skipKeys, setSkipKeys] = useState(false);

  const handleComplete = async () => {
    // Save initial settings
    const updates: SettingsUpdate = {
      ui: {
        language,
        theme: 'light',
        show_tooltips: true,
        show_tutorial: false,
        compact_mode: false,
        default_map_view: '2d',
      },
      export_profiles: {
        default_engine: defaultEngine,
        unreal5: {
          default_landscape_size: 2017,
          heightmap_format: '16bit_png',
          export_weightmaps: true,
          export_splines: true,
          generate_import_script: true,
        },
        unity: {
          default_terrain_size: 2049,
          heightmap_format: 'raw',
          export_splatmaps: true,
          export_prefabs: true,
          generate_import_script: true,
        },
        generic: {
          export_gltf: true,
          export_geotiff: true,
          export_obj: false,
          gltf_binary_format: true,
        },
      },
    };

    try {
      await settingsApi.updateSettings(updates);
      await settingsApi.completeWizard();
      onComplete();
    } catch (error) {
      console.error('Failed to save initial settings:', error);
      onComplete(); // Still complete wizard even if save fails
    }
  };

  return (
    <div className="fixed inset-0 bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center z-50 p-4">
      <div className="glass-dark rounded-2xl shadow-2xl max-w-2xl w-full p-8 text-white">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-block p-4 bg-white/20 rounded-full mb-4">
            <Rocket className="w-12 h-12" />
          </div>
          <h1 className="text-3xl font-bold mb-2">Welcome to TerraForge Studio!</h1>
          <p className="text-blue-100">Professional 3D Terrain Generator</p>
        </div>

        {/* Progress */}
        <div className="flex justify-center mb-8 space-x-2">
          {[1, 2, 3].map(i => (
            <div
              key={i}
              className={`h-2 w-16 rounded-full transition ${
                i <= step ? 'bg-white' : 'bg-white/30'
              }`}
            />
          ))}
        </div>

        {/* Step Content */}
        <div className="min-h-[300px]">
          {step === 1 && (
            <div className="space-y-6">
              <div className="flex items-center space-x-3 mb-6">
                <Globe className="w-6 h-6" />
                <h2 className="text-2xl font-semibold">Choose Your Language</h2>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <button
                  onClick={() => setLanguage('en')}
                  className={`p-6 rounded-lg border-2 transition ${
                    language === 'en'
                      ? 'border-white bg-white/20'
                      : 'border-white/30 bg-white/5 hover:bg-white/10'
                  }`}
                >
                  <div className="text-4xl mb-2">🇬🇧</div>
                  <div className="font-semibold">English</div>
                </button>

                <button
                  onClick={() => setLanguage('ru')}
                  className={`p-6 rounded-lg border-2 transition ${
                    language === 'ru'
                      ? 'border-white bg-white/20'
                      : 'border-white/30 bg-white/5 hover:bg-white/10'
                  }`}
                >
                  <div className="text-4xl mb-2">🇷🇺</div>
                  <div className="font-semibold">Русский</div>
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6">
              <div className="flex items-center space-x-3 mb-6">
                <Key className="w-6 h-6" />
                <h2 className="text-2xl font-semibold">API Keys (Optional)</h2>
              </div>

              <p className="text-blue-100 mb-6">
                TerraForge works great with free data sources (OpenStreetMap + SRTM).
                You can add premium API keys later in Settings for enhanced data quality.
              </p>

              <div className="bg-white/10 rounded-lg p-6 space-y-3">
                <h3 className="font-semibold mb-2">Free Sources (Always Available):</h3>
                <div className="flex items-center space-x-2 text-sm">
                  <Check className="w-4 h-4 text-green-300" />
                  <span>OpenStreetMap - Roads, buildings, POI</span>
                </div>
                <div className="flex items-center space-x-2 text-sm">
                  <Check className="w-4 h-4 text-green-300" />
                  <span>SRTM - Elevation data (30-90m)</span>
                </div>
              </div>

              <div className="bg-white/10 rounded-lg p-6 space-y-3">
                <h3 className="font-semibold mb-2">Premium Sources (Requires API Keys):</h3>
                <div className="text-sm space-y-1 text-blue-100">
                  <p>• Sentinel Hub - Satellite imagery (10-60m)</p>
                  <p>• OpenTopography - High-res DEMs (0.5-30m)</p>
                  <p>• Azure Maps - Vector data</p>
                </div>
              </div>

              <label className="flex items-center space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={skipKeys}
                  onChange={(e) => setSkipKeys(e.target.checked)}
                  className="rounded"
                />
                <span>Skip for now (I'll add API keys later)</span>
              </label>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-6">
              <h2 className="text-2xl font-semibold mb-6">Choose Default Export Engine</h2>

              <div className="space-y-3">
                <button
                  onClick={() => setDefaultEngine('unreal5')}
                  className={`w-full p-4 rounded-lg border-2 text-left transition ${
                    defaultEngine === 'unreal5'
                      ? 'border-white bg-white/20'
                      : 'border-white/30 bg-white/5 hover:bg-white/10'
                  }`}
                >
                  <div className="font-semibold mb-1">Unreal Engine 5</div>
                  <div className="text-sm text-blue-100">
                    Landscape heightmaps, weightmaps, and Python import scripts
                  </div>
                </button>

                <button
                  onClick={() => setDefaultEngine('unity')}
                  className={`w-full p-4 rounded-lg border-2 text-left transition ${
                    defaultEngine === 'unity'
                      ? 'border-white bg-white/20'
                      : 'border-white/30 bg-white/5 hover:bg-white/10'
                  }`}
                >
                  <div className="font-semibold mb-1">Unity</div>
                  <div className="text-sm text-blue-100">
                    Terrain heightmaps, splatmaps, and C# import scripts
                  </div>
                </button>

                <button
                  onClick={() => setDefaultEngine('generic')}
                  className={`w-full p-4 rounded-lg border-2 text-left transition ${
                    defaultEngine === 'generic'
                      ? 'border-white bg-white/20'
                      : 'border-white/30 bg-white/5 hover:bg-white/10'
                  }`}
                >
                  <div className="font-semibold mb-1">Generic (GLTF, GeoTIFF)</div>
                  <div className="text-sm text-blue-100">
                    Universal 3D formats for any software
                  </div>
                </button>
              </div>

              <p className="text-sm text-blue-100">
                💡 You can export to multiple formats at once, this is just the default selection.
              </p>
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="flex justify-between mt-8 pt-6 border-t border-white/20">
          {step > 1 ? (
            <button
              onClick={() => setStep(step - 1)}
              className="px-6 py-2 bg-white/10 hover:bg-white/20 rounded-md transition"
            >
              Back
            </button>
          ) : (
            <div />
          )}

          {step < 3 ? (
            <button
              onClick={() => setStep(step + 1)}
              className="px-6 py-2 bg-white text-blue-600 hover:bg-blue-50 rounded-md font-semibold transition"
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleComplete}
              className="px-8 py-3 bg-white text-blue-600 hover:bg-blue-50 rounded-md font-semibold transition flex items-center space-x-2"
            >
              <Rocket className="w-5 h-5" />
              <span>Get Started!</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default SetupWizard;

