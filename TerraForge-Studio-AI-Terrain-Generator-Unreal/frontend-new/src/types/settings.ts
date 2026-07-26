/**
 * Settings Types
 */

export interface SentinelHubCredentials {
  enabled: boolean;
  client_id?: string;
  client_secret?: string;
  instance_id?: string;
}

export interface OpenTopographyCredentials {
  enabled: boolean;
  api_key?: string;
}

export interface AzureMapsCredentials {
  enabled: boolean;
  subscription_key?: string;
}

export interface GoogleEarthEngineCredentials {
  enabled: boolean;
  service_account?: string;
  private_key_path?: string;
}

export interface DataSourceCredentials {
  sentinelhub: SentinelHubCredentials;
  opentopography: OpenTopographyCredentials;
  azure_maps: AzureMapsCredentials;
  google_earth_engine: GoogleEarthEngineCredentials;
}

export interface GenerationDefaults {
  default_resolution: number;
  max_area_km2: number;
  elevation_source_priority: string[];
  enable_roads: boolean;
  enable_buildings: boolean;
  enable_vegetation: boolean;
  enable_weightmaps: boolean;
  enable_water_bodies: boolean;
  parallel_processing: boolean;
  max_workers: number;
}

export interface Unreal5Profile {
  default_landscape_size: number;
  heightmap_format: string;
  export_weightmaps: boolean;
  export_splines: boolean;
  generate_import_script: boolean;
}

export interface UnityProfile {
  default_terrain_size: number;
  heightmap_format: string;
  export_splatmaps: boolean;
  export_prefabs: boolean;
  generate_import_script: boolean;
}

export interface GenericProfile {
  export_gltf: boolean;
  export_geotiff: boolean;
  export_obj: boolean;
  gltf_binary_format: boolean;
}

export interface ExportProfiles {
  unreal5: Unreal5Profile;
  unity: UnityProfile;
  generic: GenericProfile;
  default_engine: 'unreal5' | 'unity' | 'generic';
}

export interface UIPreferences {
  language: 'en' | 'ru';
  theme: 'light' | 'dark' | 'auto';
  show_tooltips: boolean;
  show_tutorial: boolean;
  compact_mode: boolean;
  default_map_view: '2d' | '3d';
}

export interface CacheSettings {
  cache_dir: string;
  output_dir: string;
  enable_cache: boolean;
  cache_expiry_days: number;
  auto_cleanup_old_projects: boolean;
  cleanup_threshold_days: number;
}

export interface AISettings {
  enabled: boolean;
  ollama_url: string;
  vision_model: string;
  coder_model: string;
  auto_analyze: boolean;
  timeout_seconds: number;
}

export interface UserSettings {
  user_name?: string;
  user_email?: string;
  credentials: DataSourceCredentials;
  generation: GenerationDefaults;
  export_profiles: ExportProfiles;
  ui: UIPreferences;
  cache: CacheSettings;
  ai?: AISettings;
  version: string;
  first_run: boolean;
}

export interface SettingsUpdate {
  credentials?: DataSourceCredentials;
  generation?: GenerationDefaults;
  export_profiles?: ExportProfiles;
  ui?: UIPreferences;
  cache?: CacheSettings;
  ai?: AISettings;
}

export interface MaskedCredentials {
  sentinelhub_enabled: boolean;
  sentinelhub_configured: boolean;
  opentopography_enabled: boolean;
  opentopography_configured: boolean;
  azure_maps_enabled: boolean;
  azure_maps_configured: boolean;
  google_earth_engine_enabled: boolean;
  google_earth_engine_configured: boolean;
}

export interface ConnectionTestResult {
  source: string;
  /** True only when a real request reached the provider and was accepted. */
  success: boolean;
  /** Credentials (if the source needs any) are present. */
  configured: boolean;
  /**
   * Whether the probe round trip completed. Null when no request was made,
   * e.g. the source is disabled or unconfigured.
   */
  reachable: boolean | null;
  error?: string | null;
  message: string;
}

