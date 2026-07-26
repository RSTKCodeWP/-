/**
 * TerraForge Studio - TypeScript Types
 */

export interface BoundingBox {
  north: number;
  south: number;
  east: number;
  west: number;
}

/**
 * Approximate area of a bounding box in km².
 *
 * Uses the same constants as the backend (`BoundingBox.area_km2`) so the area
 * shown in the UI matches the value the server validates against.
 */
export function calculateArea(bbox: BoundingBox): number {
  const avgLat = (bbox.north + bbox.south) / 2;

  const kmLat = Math.abs(bbox.north - bbox.south) * 110.574;
  const kmLon = Math.abs(bbox.east - bbox.west) * 111.32 * Math.cos((avgLat * Math.PI) / 180);

  return kmLat * kmLon;
}

export type ExportFormat = 'unreal5' | 'unity' | 'gltf' | 'geotiff' | 'obj' | 'all' | 'ue5' | 'raw16' | 'kml';
export type ElevationSource = 'srtm' | 'opentopography' | 'sentinelhub' | 'azure_maps' | 'auto' | 'sentinel';

export interface TerrainGenerationRequest {
  bbox: BoundingBox;
  name: string;
  resolution?: number;
  export_formats: ExportFormat[];
  elevation_source: ElevationSource;
  enable_ai_analysis?: boolean;
  enable_roads?: boolean;
  enable_buildings?: boolean;
  enable_vegetation?: boolean;
  enable_water_bodies?: boolean;
  enable_weightmaps?: boolean;
  enable_3d_preview?: boolean;
}

export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';

/** Where the heightmap's elevation values actually came from. */
export interface ElevationProvenance {
  source: string;
  /** True when the terrain is procedural, not measured real-world data. */
  synthetic: boolean;
  min_elevation_m: number;
  max_elevation_m: number;
}

/** Outcome of exporting to one target format. */
export interface ExportResult {
  format: string;
  success: boolean;
  directory?: string | null;
  files: Record<string, string>;
  error?: string | null;
}

export interface GenerationResult {
  terrain_name: string;
  resolution: number;
  area_km2: number;
  bbox: BoundingBox;
  elevation: ElevationProvenance;
  exports: ExportResult[];
  output_directory: string;
  thumbnail_path?: string | null;
  /** Data URI (`data:image/png;base64,...`) ready to use as an <img> src. */
  thumbnail_base64?: string | null;
  duration_seconds?: number | null;
  cached: boolean;
}

export interface GenerationStatus {
  task_id: string;
  status: TaskStatus;
  progress: number;
  current_step: string;
  message?: string | null;
  error?: string | null;
  /** Non-fatal issues, e.g. a single export format that failed. */
  warnings: string[];
  download_url?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  result?: GenerationResult | null;
}

/** Response shape of `GET /api/tasks`. */
export interface TaskListResponse {
  count: number;
  tasks: GenerationStatus[];
}

export interface DataSource {
  name: string;
  resolution: string;
  coverage: string;
  cost: string;
  available: boolean;
  requires_api_key: boolean;
}

export interface ExportFormatInfo {
  name: string;
  description: string;
  files: string[];
  valid_resolutions: number[] | string;
  supports_weightmaps: boolean;
  supports_roads: boolean;
  supports_buildings: boolean;
}

export interface HealthStatus {
  status: string;
  version: string;
  environment?: string;
  data_sources: {
    available: string[];
    configured?: string[];
    total: number;
  };
  settings: {
    max_area_km2: number;
    default_resolution: number;
    synthetic_fallback?: boolean;
  };
}

export interface SourcesResponse {
  elevation: Record<string, DataSource>;
  imagery: Record<string, DataSource>;
  vector: Record<string, DataSource>;
}

export interface FormatsResponse {
  formats: Record<string, ExportFormatInfo>;
}

