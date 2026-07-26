import { useState } from 'react';
import { Loader } from 'lucide-react';
import type { ExportProfiles } from '@/types/settings';

interface ExportProfilesTabProps {
  profiles: ExportProfiles;
  onSave: (profiles: ExportProfiles) => void;
  saving: boolean;
}

const ExportProfilesTab: React.FC<ExportProfilesTabProps> = ({ profiles, onSave, saving }) => {
  const defaultProfiles: ExportProfiles = {
    unreal5: {
      default_landscape_size: 8129,
      heightmap_format: 'png16',
      export_weightmaps: true,
      export_splines: false,
      generate_import_script: true,
    },
    unity: {
      default_terrain_size: 2000,
      heightmap_format: 'png16',
      export_splatmaps: true,
      export_prefabs: false,
      generate_import_script: true,
    },
    generic: {
      export_gltf: true,
      export_geotiff: true,
      export_obj: false,
      gltf_binary_format: true,
    },
    default_engine: 'unreal5',
  };

  const [formData, setFormData] = useState<ExportProfiles>({
    ...defaultProfiles,
    ...profiles,
    unreal5: { ...defaultProfiles.unreal5, ...profiles?.unreal5 },
    unity: { ...defaultProfiles.unity, ...profiles?.unity },
    generic: { ...defaultProfiles.generic, ...profiles?.generic },
  });

  return (
    <div className="space-y-6">
      <h3 className="text-xl font-semibold">Export Profiles</h3>

      {/* Unreal Engine 5 */}
      <div className="bg-white rounded-lg p-6 border border-gray-200 space-y-4">
        <h4 className="font-semibold text-lg">Unreal Engine 5</h4>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Landscape Size</label>
            <select
              value={formData.unreal5.default_landscape_size}
              onChange={(e) => setFormData({
                ...formData,
                unreal5: { ...formData.unreal5, default_landscape_size: Number(e.target.value) }
              })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value={2017}>2017x2017</option>
              <option value={4033}>4033x4033</option>
              <option value={8129}>8129x8129</option>
            </select>
          </div>

          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.unreal5.export_weightmaps}
              onChange={(e) => setFormData({
                ...formData,
                unreal5: { ...formData.unreal5, export_weightmaps: e.target.checked }
              })}
              className="rounded text-blue-600"
            />
            <span className="ml-2 text-sm">Export Weightmaps</span>
          </label>

          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.unreal5.export_splines}
              onChange={(e) => setFormData({
                ...formData,
                unreal5: { ...formData.unreal5, export_splines: e.target.checked }
              })}
              className="rounded text-blue-600"
            />
            <span className="ml-2 text-sm">Export Splines (Roads)</span>
          </label>

          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.unreal5.generate_import_script}
              onChange={(e) => setFormData({
                ...formData,
                unreal5: { ...formData.unreal5, generate_import_script: e.target.checked }
              })}
              className="rounded text-blue-600"
            />
            <span className="ml-2 text-sm">Generate Import Script</span>
          </label>
        </div>
      </div>

      {/* Unity */}
      <div className="bg-white rounded-lg p-6 border border-gray-200 space-y-4">
        <h4 className="font-semibold text-lg">Unity</h4>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Terrain Size (m)</label>
            <input
              type="number"
              value={formData.unity.default_terrain_size}
              onChange={(e) => setFormData({
                ...formData,
                unity: { ...formData.unity, default_terrain_size: Number(e.target.value) }
              })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              placeholder="2000"
            />
          </div>

          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.unity.export_splatmaps}
              onChange={(e) => setFormData({
                ...formData,
                unity: { ...formData.unity, export_splatmaps: e.target.checked }
              })}
              className="rounded text-blue-600"
            />
            <span className="ml-2 text-sm">Export Splatmaps (Textures)</span>
          </label>

          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.unity.export_prefabs}
              onChange={(e) => setFormData({
                ...formData,
                unity: { ...formData.unity, export_prefabs: e.target.checked }
              })}
              className="rounded text-blue-600"
            />
            <span className="ml-2 text-sm">Export Prefabs (Trees/Buildings)</span>
          </label>

          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.unity.generate_import_script}
              onChange={(e) => setFormData({
                ...formData,
                unity: { ...formData.unity, generate_import_script: e.target.checked }
              })}
              className="rounded text-blue-600"
            />
            <span className="ml-2 text-sm">Generate Import Script</span>
          </label>
        </div>
      </div>

      {/* Generic (GLTF/GeoTIFF/OBJ) */}
      <div className="bg-white rounded-lg p-6 border border-gray-200 space-y-4">
        <h4 className="font-semibold text-lg">Generic Export (GLTF/GeoTIFF/OBJ)</h4>
        <div className="space-y-3">
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.generic.export_gltf}
              onChange={(e) => setFormData({
                ...formData,
                generic: { ...formData.generic, export_gltf: e.target.checked }
              })}
              className="rounded text-blue-600"
            />
            <span className="ml-2 text-sm">Export GLTF/GLB</span>
          </label>

          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.generic.gltf_binary_format}
              onChange={(e) => setFormData({
                ...formData,
                generic: { ...formData.generic, gltf_binary_format: e.target.checked }
              })}
              className="rounded text-blue-600"
              disabled={!formData.generic.export_gltf}
            />
            <span className="ml-2 text-sm">Use Binary Format (.glb)</span>
          </label>

          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.generic.export_geotiff}
              onChange={(e) => setFormData({
                ...formData,
                generic: { ...formData.generic, export_geotiff: e.target.checked }
              })}
              className="rounded text-blue-600"
            />
            <span className="ml-2 text-sm">Export GeoTIFF</span>
          </label>

          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.generic.export_obj}
              onChange={(e) => setFormData({
                ...formData,
                generic: { ...formData.generic, export_obj: e.target.checked }
              })}
              className="rounded text-blue-600"
            />
            <span className="ml-2 text-sm">Export OBJ</span>
          </label>
        </div>
      </div>

      <div className="flex justify-end pt-6 border-t">
        <button
          onClick={() => onSave(formData)}
          disabled={saving}
          className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
        >
          {saving && <Loader className="w-4 h-4 animate-spin mr-2" />}
          Save Profiles
        </button>
      </div>
    </div>
  );
};

export default ExportProfilesTab;

