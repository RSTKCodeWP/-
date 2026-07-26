/**
 * Generation Status Monitor
 */

import { CheckCircle, XCircle, Loader, Download, AlertTriangle } from 'lucide-react';
import { terraforgeApi } from '@/services/api';
import type { GenerationStatus } from '@/types';

interface StatusMonitorProps {
  status: GenerationStatus;
}

const StatusMonitor: React.FC<StatusMonitorProps> = ({ status }) => {
  const getStatusIcon = () => {
    switch (status.status) {
      case 'completed':
        return <CheckCircle className="w-6 h-6 text-green-500" />;
      case 'failed':
        return <XCircle className="w-6 h-6 text-red-500" />;
      default:
        return <Loader className="w-6 h-6 text-blue-500 animate-spin" />;
    }
  };

  const getStatusColor = () => {
    switch (status.status) {
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      case 'processing':
        return 'bg-blue-500';
      default:
        return 'bg-gray-300 dark:bg-gray-600';
    }
  };

  return (
    <div className="space-y-4">
      {/* Status Header */}
      <div className="flex items-center space-x-3">
        {getStatusIcon()}
        <div className="flex-1">
          <p className="font-semibold text-gray-900 dark:text-white capitalize">{status.status}</p>
          <p className="text-sm text-gray-600 dark:text-gray-400">{status.current_step}</p>
        </div>
      </div>

      {/* Progress Bar */}
      {status.status === 'processing' && (
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400">
            <span>Progress</span>
            <span>{status.progress.toFixed(0)}%</span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div
              className={`${getStatusColor()} h-2 rounded-full transition-all duration-300`}
              style={{ width: `${status.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Error Message */}
      {status.error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md p-3">
          <p className="text-sm text-red-800 dark:text-red-200">{status.error}</p>
        </div>
      )}

      {/* Non-fatal warnings, e.g. a format that failed or synthetic elevation */}
      {status.warnings?.length > 0 && (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-md p-3 space-y-1">
          {status.warnings.map((warning, index) => (
            <p
              key={index}
              className="flex items-start gap-2 text-sm text-amber-800 dark:text-amber-200"
            >
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{warning}</span>
            </p>
          ))}
        </div>
      )}

      {/* Success Result */}
      {status.result && (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-md p-4 space-y-3">
          <h4 className="font-semibold text-green-900 dark:text-green-100">Generation Complete!</h4>

          <div className="text-sm text-green-800 dark:text-green-200 space-y-1">
            <p><strong>Terrain:</strong> {status.result.terrain_name}</p>
            <p><strong>Resolution:</strong> {status.result.resolution}x{status.result.resolution}</p>
            <p><strong>Area:</strong> {status.result.area_km2.toFixed(2)} km²</p>
            <p>
              <strong>Elevation:</strong> {status.result.elevation.min_elevation_m.toFixed(1)}m
              {' - '}{status.result.elevation.max_elevation_m.toFixed(1)}m
              {' '}
              <span className="opacity-75">
                ({status.result.elevation.synthetic
                  ? 'synthetic'
                  : `source: ${status.result.elevation.source}`})
              </span>
            </p>
            {status.result.duration_seconds != null && (
              <p><strong>Duration:</strong> {status.result.duration_seconds.toFixed(1)}s</p>
            )}
          </div>

          {/* Export Downloads */}
          <div className="pt-3 border-t border-green-300 dark:border-green-700">
            <p className="text-sm font-semibold text-green-900 dark:text-green-100 mb-2">Exports:</p>
            <div className="space-y-2">
              {status.result.exports.filter(exp => exp.success).map(exp => (
                <a
                  key={exp.format}
                  href={terraforgeApi.downloadUrl(status.result!.terrain_name, 'zip')}
                  className="flex items-center justify-between px-3 py-2 bg-white dark:bg-gray-800 rounded-md hover:bg-green-100 dark:hover:bg-green-900/30 transition"
                >
                  <span className="text-sm text-gray-700 dark:text-gray-300 capitalize">{exp.format}</span>
                  <Download className="w-4 h-4 text-green-600 dark:text-green-400" />
                </a>
              ))}
              {status.result.exports.filter(exp => !exp.success).map(exp => (
                <div
                  key={exp.format}
                  className="px-3 py-2 bg-white dark:bg-gray-800 rounded-md opacity-60"
                >
                  <span className="text-sm text-gray-500 dark:text-gray-400 capitalize">
                    {exp.format} - failed
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default StatusMonitor;
