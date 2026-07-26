/**
 * Preset Types and Definitions
 */

import type { ExportFormat, ElevationSource } from './index';

export interface TerrainPreset {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: 'gaming' | 'professional' | 'planning' | 'general';
  config: {
    resolution: number;
    exportFormats: ExportFormat[];
    elevationSource: ElevationSource;
    enableRoads: boolean;
    enableBuildings: boolean;
    enableWeightmaps: boolean;
    enableVegetation: boolean;
    enableWaterBodies: boolean;
  };
  tags: string[];
}

export const BUILT_IN_PRESETS: TerrainPreset[] = [
  {
    id: 'mountain-landscape',
    name: 'Mountain Landscape',
    description: 'High-detail terrain for mountainous regions with full vegetation and water features',
    icon: '🏔️',
    category: 'general',
    config: {
      resolution: 2048,
      exportFormats: ['gltf', 'geotiff'],
      elevationSource: 'opentopography',
      enableRoads: true,
      enableBuildings: false,
      enableWeightmaps: true,
      enableVegetation: true,
      enableWaterBodies: true,
    },
    tags: ['nature', 'outdoor', 'hiking'],
  },
  {
    id: 'urban-planning',
    name: 'Urban Planning',
    description: 'Focused on buildings, roads, and urban infrastructure',
    icon: '🏙️',
    category: 'planning',
    config: {
      resolution: 1024,
      exportFormats: ['geotiff', 'obj'],
      elevationSource: 'sentinel',
      enableRoads: true,
      enableBuildings: true,
      enableWeightmaps: false,
      enableVegetation: false,
      enableWaterBodies: true,
    },
    tags: ['city', 'urban', 'planning', 'infrastructure'],
  },
  {
    id: 'ue5-game',
    name: 'Unreal Engine 5',
    description: 'Optimized for Unreal Engine 5 with weightmaps and game-ready assets',
    icon: '🎮',
    category: 'gaming',
    config: {
      resolution: 2048,
      exportFormats: ['ue5', 'gltf'],
      elevationSource: 'opentopography',
      enableRoads: true,
      enableBuildings: true,
      enableWeightmaps: true,
      enableVegetation: true,
      enableWaterBodies: true,
    },
    tags: ['ue5', 'unreal', 'gaming', 'game-dev'],
  },
  {
    id: 'unity-game',
    name: 'Unity Terrain',
    description: 'Optimized for Unity with terrain layers and splat maps',
    icon: '🎯',
    category: 'gaming',
    config: {
      resolution: 1024,
      exportFormats: ['unity', 'raw16'],
      elevationSource: 'opentopography',
      enableRoads: true,
      enableBuildings: true,
      enableWeightmaps: true,
      enableVegetation: true,
      enableWaterBodies: true,
    },
    tags: ['unity', 'gaming', 'game-dev'],
  },
  {
    id: 'gis-analysis',
    name: 'GIS Analysis',
    description: 'Professional GIS output with GeoTIFF and accurate georeferencing',
    icon: '🗺️',
    category: 'professional',
    config: {
      resolution: 4096,
      exportFormats: ['geotiff', 'kml'],
      elevationSource: 'opentopography',
      enableRoads: true,
      enableBuildings: true,
      enableWeightmaps: false,
      enableVegetation: true,
      enableWaterBodies: true,
    },
    tags: ['gis', 'analysis', 'professional', 'mapping'],
  },
  {
    id: 'quick-preview',
    name: 'Quick Preview',
    description: 'Fast generation with lower resolution for testing',
    icon: '⚡',
    category: 'general',
    config: {
      resolution: 512,
      exportFormats: ['gltf'],
      elevationSource: 'sentinel',
      enableRoads: false,
      enableBuildings: false,
      enableWeightmaps: false,
      enableVegetation: false,
      enableWaterBodies: false,
    },
    tags: ['quick', 'test', 'preview', 'fast'],
  },
  {
    id: 'coastal-region',
    name: 'Coastal Region',
    description: 'Optimized for coastal areas with water bodies and beach features',
    icon: '🏖️',
    category: 'general',
    config: {
      resolution: 2048,
      exportFormats: ['gltf', 'geotiff'],
      elevationSource: 'opentopography',
      enableRoads: true,
      enableBuildings: true,
      enableWeightmaps: true,
      enableVegetation: true,
      enableWaterBodies: true,
    },
    tags: ['coast', 'beach', 'ocean', 'water'],
  },
  {
    id: 'simulation-training',
    name: 'Simulation & Training',
    description: 'High-fidelity terrain for training simulations',
    icon: '🎓',
    category: 'professional',
    config: {
      resolution: 2048,
      exportFormats: ['gltf', 'ue5'],
      elevationSource: 'opentopography',
      enableRoads: true,
      enableBuildings: true,
      enableWeightmaps: true,
      enableVegetation: true,
      enableWaterBodies: true,
    },
    tags: ['simulation', 'training', 'military', 'education'],
  },
];

