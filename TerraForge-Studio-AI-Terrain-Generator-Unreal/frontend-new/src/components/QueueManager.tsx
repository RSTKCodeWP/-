/**
 * Queue Manager Component
 * Displays and manages the batch processing queue
 */

import { useState, useEffect } from 'react';
import { RefreshCw, Trash2, X, Download, RotateCcw, CheckCircle, XCircle, Clock, Loader } from 'lucide-react';

interface BatchJob {
  id: string;
  name: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  error?: string;
  result?: Record<string, unknown>;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

interface QueueManagerProps {
  onClose: () => void;
}

const QueueManager: React.FC<QueueManagerProps> = ({ onClose }) => {
  const [jobs, setJobs] = useState<BatchJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState({
    total_jobs: 0,
    pending: 0,
    processing: 0,
    completed: 0,
    failed: 0,
  });

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/batch/jobs');
      const data = await response.json();
      setJobs(data);
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch('/api/batch/stats');
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  };

  useEffect(() => {
    fetchJobs();
    fetchStats();
    
    // Poll every 5 seconds
    const interval = setInterval(() => {
      fetchJobs();
      fetchStats();
    }, 5000);
    
    return () => clearInterval(interval);
  }, []);

  const cancelJob = async (jobId: string) => {
    try {
      await fetch(`/api/batch/jobs/${jobId}/cancel`, { method: 'POST' });
      fetchJobs();
    } catch (error) {
      console.error('Failed to cancel job:', error);
    }
  };

  const retryJob = async (jobId: string) => {
    try {
      await fetch(`/api/batch/jobs/${jobId}/retry`, { method: 'POST' });
      fetchJobs();
    } catch (error) {
      console.error('Failed to retry job:', error);
    }
  };

  const clearCompleted = async () => {
    try {
      await fetch('/api/batch/clear', { method: 'POST' });
      fetchJobs();
      fetchStats();
    } catch (error) {
      console.error('Failed to clear completed:', error);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'processing':
        return <Loader className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'cancelled':
        return <X className="w-5 h-5 text-gray-500" />;
      default:
        return <Clock className="w-5 h-5 text-gray-400" />;
    }
  };

  const downloadResult = async (jobId: string, _jobName: string) => {
    try {
      const response = await fetch(`/api/batch/downloads/${jobId}`);
      const data = await response.json();
      
      // Open first download link
      if (data.downloads && data.downloads.length > 0) {
        window.open(data.downloads[0].url, '_blank');
      }
    } catch (error) {
      console.error('Failed to download:', error);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="glass max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-lg p-6 shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          Generation Queue
        </h2>
        <div className="flex space-x-2">
          <button
            onClick={fetchJobs}
            disabled={loading}
            className="p-2 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={clearCompleted}
            className="flex items-center space-x-1 px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition"
          >
            <Trash2 className="w-4 h-4" />
            <span>Clear Completed</span>
          </button>
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-2 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{stats.total_jobs}</div>
          <div className="text-xs text-gray-600 dark:text-gray-400">Total</div>
        </div>
        <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
          <div className="text-2xl font-bold text-gray-600 dark:text-gray-400">{stats.pending}</div>
          <div className="text-xs text-gray-600 dark:text-gray-400">Pending</div>
        </div>
        <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{stats.processing}</div>
          <div className="text-xs text-gray-600 dark:text-gray-400">Processing</div>
        </div>
        <div className="text-center p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
          <div className="text-2xl font-bold text-green-600 dark:text-green-400">{stats.completed}</div>
          <div className="text-xs text-gray-600 dark:text-gray-400">Completed</div>
        </div>
        <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
          <div className="text-2xl font-bold text-red-600 dark:text-red-400">{stats.failed}</div>
          <div className="text-xs text-gray-600 dark:text-gray-400">Failed</div>
        </div>
      </div>

      {/* Job List */}
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {jobs.length === 0 ? (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            No jobs in queue
          </div>
        ) : (
          jobs.map(job => (
            <div
              key={job.id}
              className="flex items-center justify-between p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:shadow-md transition"
            >
              <div className="flex items-center space-x-4 flex-1">
                {getStatusIcon(job.status)}
                
                <div className="flex-1">
                  <div className="font-medium text-gray-900 dark:text-white">{job.name}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 capitalize">{job.status}</div>
                  
                  {job.status === 'processing' && (
                    <div className="mt-2 w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                      <div
                        className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                        style={{ width: `${job.progress}%` }}
                      />
                    </div>
                  )}
                  
                  {job.error && (
                    <div className="mt-1 text-xs text-red-600 dark:text-red-400">{job.error}</div>
                  )}
                </div>

                <div className="text-sm text-gray-600 dark:text-gray-400">
                  {job.status === 'processing' && `${job.progress.toFixed(0)}%`}
                </div>
              </div>

              <div className="flex space-x-2 ml-4">
                {job.status === 'completed' && (
                  <button
                    onClick={() => downloadResult(job.id, job.name)}
                    className="p-2 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 rounded-md transition"
                    title="Download"
                  >
                    <Download className="w-4 h-4" />
                  </button>
                )}
                
                {job.status === 'failed' && (
                  <button
                    onClick={() => retryJob(job.id)}
                    className="p-2 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-md transition"
                    title="Retry"
                  >
                    <RotateCcw className="w-4 h-4" />
                  </button>
                )}
                
                {(job.status === 'pending' || job.status === 'processing') && (
                  <button
                    onClick={() => cancelJob(job.id)}
                    className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition"
                    title="Cancel"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
      </div>
    </div>
  );
};

export default QueueManager;

