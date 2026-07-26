import { useState } from 'react';
import { Loader } from 'lucide-react';
import type { GenerationDefaults } from '@/types/settings';

interface GenerationTabProps {
  generation: GenerationDefaults;
  onSave: (generation: GenerationDefaults) => void;
  saving: boolean;
}

const GenerationTab: React.FC<GenerationTabProps> = ({ generation, onSave, saving }) => {
  const defaultGeneration: GenerationDefaults = {
    default_resolution: 2048,
    max_area_km2: 100,
    elevation_source_priority: ['auto'],
    enable_roads: true,
    enable_buildings: true,
    enable_vegetation: true,
    enable_weightmaps: true,
    enable_water_bodies: true,
    parallel_processing: true,
    max_workers: 4,
  };

  const [formData, setFormData] = useState<GenerationDefaults>({
    ...defaultGeneration,
    ...generation,
  });

  return (
    <div className="space-y-6">
      <h3 className="text-xl font-semibold">Generation Defaults</h3>

      <div className="grid grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Default Resolution
          </label>
          <select
            value={formData.default_resolution}
            onChange={(e) => setFormData({ ...formData, default_resolution: Number(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md"
          >
            <option value={1024}>1024</option>
            <option value={2048}>2048</option>
            <option value={4096}>4096</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Max Area (km²)
          </label>
          <input
            type="number"
            value={formData.max_area_km2}
            onChange={(e) => setFormData({ ...formData, max_area_km2: Number(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md"
            min="1"
            max="500"
          />
        </div>
      </div>

      <div className="flex justify-end pt-6 border-t">
        <button
          onClick={() => onSave(formData)}
          disabled={saving}
          className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center space-x-2"
        >
          {saving && <Loader className="w-4 h-4 animate-spin" />}
          <span>Save Settings</span>
        </button>
      </div>
    </div>
  );
};

export default GenerationTab;

