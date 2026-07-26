import { useState } from 'react';
import { Loader } from 'lucide-react';
import type { CacheSettings } from '@/types/settings';

interface CacheStorageTabProps {
  cache: CacheSettings;
  onSave: (cache: CacheSettings) => void;
  saving: boolean;
}

const CacheStorageTab: React.FC<CacheStorageTabProps> = ({ cache, onSave, saving }) => {
  const defaultCache: CacheSettings = {
    cache_dir: './cache',
    output_dir: './output',
    enable_cache: true,
    cache_expiry_days: 30,
    auto_cleanup_old_projects: true,
    cleanup_threshold_days: 90,
  };

  const [formData, setFormData] = useState<CacheSettings>({
    ...defaultCache,
    ...cache,
  });

  return (
    <div className="space-y-6">
      <h3 className="text-xl font-semibold">Cache & Storage</h3>

      <div className="space-y-4">
        <label className="flex items-center">
          <input
            type="checkbox"
            checked={formData.enable_cache}
            onChange={(e) => setFormData({ ...formData, enable_cache: e.target.checked })}
            className="rounded text-blue-600"
          />
          <span className="ml-2">Enable Cache</span>
        </label>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Cache Expiry (days)
          </label>
          <input
            type="number"
            value={formData.cache_expiry_days}
            onChange={(e) => setFormData({ ...formData, cache_expiry_days: Number(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md"
            min="1"
            max="365"
          />
        </div>
      </div>

      <div className="flex justify-end pt-6 border-t">
        <button onClick={() => onSave(formData)} disabled={saving} className="px-6 py-3 bg-blue-600 text-white rounded-md">
          {saving && <Loader className="w-4 h-4 animate-spin mr-2" />}
          Save Storage Settings
        </button>
      </div>
    </div>
  );
};

export default CacheStorageTab;

