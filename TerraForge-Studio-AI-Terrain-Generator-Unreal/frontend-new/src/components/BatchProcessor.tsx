/**
 * Batch Processor Component
 * Manages multiple terrain generation jobs in a queue
 */

import { useState } from 'react';
import { Plus, Upload, Download, X } from 'lucide-react';
import type { BoundingBox, ExportFormat, ElevationSource } from '@/types';

interface BatchJobInput {
  id: string;
  name: string;
  bbox: BoundingBox | null;
  resolution: number;
  exportFormats: ExportFormat[];
  elevationSource: ElevationSource;
}

interface BatchProcessorProps {
  onSubmitBatch: (jobs: BatchJobInput[]) => void;
}

const BatchProcessor: React.FC<BatchProcessorProps> = ({ onSubmitBatch }) => {
  const [jobs, setJobs] = useState<BatchJobInput[]>([]);

  const addNewJob = () => {
    const newJob: BatchJobInput = {
      id: `job_${Date.now()}`,
      name: `terrain_${jobs.length + 1}`,
      bbox: null,
      resolution: 2048,
      exportFormats: ['unreal5'],
      elevationSource: 'auto',
    };
    setJobs([...jobs, newJob]);
    // setShowAddForm(false); // Commented out - form management to be implemented
  };

  const removeJob = (id: string) => {
    setJobs(jobs.filter(j => j.id !== id));
  };

  const updateJob = (id: string, updates: Partial<BatchJobInput>) => {
    setJobs(jobs.map(j => j.id === id ? { ...j, ...updates } : j));
  };

  const handleImportCSV = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const lines = text.split('\n').filter(l => l.trim());
      
      // Skip header
      const dataLines = lines.slice(1);
      
      const imported: BatchJobInput[] = dataLines.map((line, idx) => {
        const [name, north, south, east, west, resolution, formats] = line.split(',');
        return {
          id: `imported_${Date.now()}_${idx}`,
          name: name.trim(),
          bbox: {
            north: parseFloat(north),
            south: parseFloat(south),
            east: parseFloat(east),
            west: parseFloat(west),
          },
          resolution: parseInt(resolution) || 2048,
          exportFormats: formats.split('|').map(f => f.trim()) as ExportFormat[],
          elevationSource: 'auto' as ElevationSource,
        };
      });

      setJobs([...jobs, ...imported]);
    };
    reader.readAsText(file);
  };

  return (
    <div className="glass rounded-lg p-6 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          Batch Processing
        </h2>
        <div className="flex space-x-2">
          <label className="flex items-center space-x-2 px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 cursor-pointer transition">
            <Upload className="w-4 h-4" />
            <span className="text-sm">Import CSV</span>
            <input
              type="file"
              accept=".csv"
              onChange={handleImportCSV}
              className="hidden"
            />
          </label>
          <button
            onClick={addNewJob}
            className="flex items-center space-x-2 px-3 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition"
          >
            <Plus className="w-4 h-4" />
            <span className="text-sm">Add Job</span>
          </button>
        </div>
      </div>

      {jobs.length === 0 ? (
        <div className="text-center py-12 text-gray-500 dark:text-gray-400">
          <p>No jobs in batch queue</p>
          <p className="text-sm mt-2">Add jobs manually or import from CSV</p>
        </div>
      ) : (
        <>
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {jobs.map(job => (
              <div
                key={job.id}
                className="flex items-center justify-between p-3 bg-white dark:bg-gray-800 rounded-md border border-gray-200 dark:border-gray-700"
              >
                <div className="flex-1 grid grid-cols-4 gap-3">
                  <input
                    type="text"
                    value={job.name}
                    onChange={(e) => updateJob(job.id, { name: e.target.value })}
                    className="px-2 py-1 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="Terrain name"
                  />
                  <select
                    value={job.resolution}
                    onChange={(e) => updateJob(job.id, { resolution: Number(e.target.value) })}
                    className="px-2 py-1 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  >
                    <option value={1009}>1009</option>
                    <option value={2048}>2048</option>
                    <option value={4096}>4096</option>
                  </select>
                  <div className="text-xs text-gray-600 dark:text-gray-400 flex items-center">
                    {job.bbox ? (
                      <span className="text-green-600 dark:text-green-400">✓ Area selected</span>
                    ) : (
                      <span className="text-orange-600 dark:text-orange-400">⚠ No area</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-600 dark:text-gray-400 flex items-center">
                    {job.exportFormats.join(', ')}
                  </div>
                </div>
                <button
                  onClick={() => removeJob(job.id)}
                  className="ml-3 p-1 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>

          <div className="mt-6 flex items-center justify-between pt-4 border-t border-gray-200 dark:border-gray-700">
            <div className="text-sm text-gray-600 dark:text-gray-400">
              {jobs.length} job{jobs.length !== 1 ? 's' : ''} in queue
            </div>
            <button
              onClick={() => onSubmitBatch(jobs)}
              disabled={jobs.length === 0}
              className="flex items-center space-x-2 px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition"
            >
              <Download className="w-4 h-4" />
              <span>Submit Batch</span>
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default BatchProcessor;

