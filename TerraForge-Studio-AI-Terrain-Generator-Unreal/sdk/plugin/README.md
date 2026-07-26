# TerraForge Plugin SDK

Build custom exporters and extensions for TerraForge Studio.

## Installation

```bash
npm install @terraforge/plugin-sdk
```

## Quick Start

### Create Custom Exporter

```typescript
import { ExporterPlugin, ExportRequest, ExportResult } from '@terraforge/plugin-sdk';

export class MyCustomExporter implements ExporterPlugin {
  config = {
    format: 'custom',
    category: 'game-engine',
    name: 'My Custom Format',
    description: 'Export to my custom format',
    version: '1.0.0',
    fileExtension: '.custom',
    mimeType: 'application/custom',
    supports: {
      heightmap: true,
      texture: true,
      mesh: false,
      metadata: true,
    },
    options: [
      {
        id: 'quality',
        name: 'Quality',
        type: 'select',
        defaultValue: 'high',
        options: [
          { label: 'Low', value: 'low' },
          { label: 'High', value: 'high' },
        ],
      },
    ],
  };

  async export(request: ExportRequest): Promise<ExportResult> {
    // Your export logic here
    const data = this.convertTerrain(request);
    
    return {
      id: `export_${Date.now()}`,
      format: 'custom',
      status: 'completed',
      progress: 100,
      fileSize: data.length,
      createdAt: Date.now(),
      completedAt: Date.now(),
    };
  }

  validate(request: ExportRequest): boolean {
    return request.bbox !== undefined;
  }

  private convertTerrain(request: ExportRequest): Uint8Array {
    // Conversion logic
    return new Uint8Array([]);
  }
}
```

## API Reference

### ExporterPlugin Interface

```typescript
interface ExporterPlugin {
  config: ExporterConfig;
  export(request: ExportRequest): Promise<ExportResult>;
  validate(request: ExportRequest): boolean;
}
```

### ExporterConfig

```typescript
interface ExporterConfig {
  format: string;
  category: 'game-engine' | 'ar-vr' | 'cad' | 'gis' | 'other';
  name: string;
  description: string;
  version: string;
  fileExtension: string;
  mimeType: string;
  supports: {
    heightmap: boolean;
    texture: boolean;
    mesh: boolean;
    metadata: boolean;
  };
  options: ExporterOption[];
}
```

### ExportRequest

```typescript
interface ExportRequest {
  bbox: BoundingBox;
  resolution: number;
  heightmapUrl?: string;
  textureUrl?: string;
  options: Record<string, any>;
}
```

### ExportResult

```typescript
interface ExportResult {
  id: string;
  format: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  downloadUrl?: string;
  fileSize?: number;
  createdAt: number;
  completedAt?: number;
  error?: string;
}
```

## Publishing Your Plugin

1. Build your plugin:
```bash
npm run build
```

2. Publish to npm:
```bash
npm publish
```

3. Register in TerraForge Marketplace:
```bash
terraforge plugin publish
```

## Examples

See `/examples` directory for complete plugin examples:
- `blender-exporter/` - Blender integration
- `3ds-max-exporter/` - 3DS Max format
- `custom-processor/` - Custom terrain processing

## Support

- Documentation: https://docs.terraforge.studio/plugin-sdk
- Discord: https://discord.gg/terraforge
- GitHub: https://github.com/terraforge/plugin-sdk
