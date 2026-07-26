/**
 * TerraForge Studio - API Service
 */

import axios from 'axios';
import type {
  TerrainGenerationRequest,
  GenerationStatus,
  HealthStatus,
  SourcesResponse,
  FormatsResponse,
  TaskListResponse,
} from '@/types';

// Use empty baseURL to make requests relative to current origin
// This works for both dev (with proxy) and production (served from same origin)
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Export for use in other services
export { api };

export const terraforgeApi = {
  // Health check
  getHealth: async (): Promise<HealthStatus> => {
    const response = await api.get<HealthStatus>('/api/health');
    return response.data;
  },

  // Get available data sources
  getSources: async (): Promise<SourcesResponse> => {
    const response = await api.get<SourcesResponse>('/api/sources');
    return response.data;
  },

  // Get available export formats
  getFormats: async (): Promise<FormatsResponse> => {
    const response = await api.get<FormatsResponse>('/api/formats');
    return response.data;
  },

  // Generate terrain
  generateTerrain: async (request: TerrainGenerationRequest): Promise<GenerationStatus> => {
    const response = await api.post<GenerationStatus>('/api/generate', request);
    return response.data;
  },

  // Get generation status
  getStatus: async (taskId: string): Promise<GenerationStatus> => {
    const response = await api.get<GenerationStatus>(`/api/status/${taskId}`);
    return response.data;
  },

  // List all tasks. The endpoint wraps the list in { count, tasks }.
  listTasks: async (): Promise<GenerationStatus[]> => {
    const response = await api.get<TaskListResponse>('/api/tasks');
    return response.data.tasks;
  },

  /**
   * URL of a downloadable artifact for a generated map.
   *
   * `fileType` is one of the keys the backend exposes: 'zip' for the whole
   * map, or 'heightmap' / 'metadata' / 'thumbnail' for individual files.
   */
  downloadUrl: (mapName: string, fileType: string = 'zip'): string => {
    return `${API_BASE_URL}/api/maps/${encodeURIComponent(mapName)}/download/${fileType}`;
  },
};

export default terraforgeApi;

