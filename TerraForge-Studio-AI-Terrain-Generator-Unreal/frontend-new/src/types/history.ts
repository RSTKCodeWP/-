/**
 * Generation History Types
 */

import type { BoundingBox, ExportFormat, ElevationSource } from './index';

export interface GenerationHistoryItem {
  id: string;
  timestamp: number;
  name: string;
  bbox: BoundingBox;
  config: {
    resolution: number;
    exportFormats: ExportFormat[];
    elevationSource: ElevationSource;
    enableRoads: boolean;
    enableBuildings: boolean;
    enableWeightmaps: boolean;
  };
  status: 'completed' | 'failed' | 'partial';
  thumbnail?: string;
  downloadUrl?: string;
  stats?: {
    duration?: number;
    fileSize?: number;
    terrainArea?: number;
  };
}

