/**
 * Share Link Types
 * Types for project sharing and collaboration
 */

import type { BoundingBox, ExportFormat, ElevationSource } from './index';

export interface ShareLink {
  id: string;
  shortId: string;
  createdAt: number;
  expiresAt?: number;
  accessCount: number;
  maxAccess?: number;
  isActive: boolean;
  config: ShareConfig;
  metadata: ShareMetadata;
}

export interface ShareConfig {
  bbox: BoundingBox;
  name: string;
  resolution: number;
  exportFormats: ExportFormat[];
  elevationSource: ElevationSource;
  enableRoads: boolean;
  enableBuildings: boolean;
  enableWeightmaps: boolean;
  presetId?: string;
}

export interface ShareMetadata {
  createdBy?: string;
  title?: string;
  description?: string;
  thumbnail?: string;
  tags?: string[];
}

export interface ShareOptions {
  expiresIn?: number; // milliseconds
  maxAccess?: number;
  requireAuth?: boolean;
  allowEdit?: boolean;
}

export interface ShareLinkResponse {
  shareLink: ShareLink;
  url: string;
  shortUrl: string;
}

