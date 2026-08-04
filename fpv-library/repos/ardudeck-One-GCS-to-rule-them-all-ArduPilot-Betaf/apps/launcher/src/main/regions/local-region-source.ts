import { readdir, readFile, stat } from 'node:fs/promises';
import { join } from 'node:path';
import {
  parseRegionManifest,
  regionDisplayName,
  type PreparedRegion,
  type RegionSource,
  type RegionSummary,
} from '../../shared/region.js';

/**
 * Files `load_terrain_data` needs before a region renders anything at all. Everything else
 * the bake produces (canopy, tree_mask, buildings, infra, species) is optional by design and
 * the game falls back procedurally, so their absence is not worth surfacing.
 */
const REQUIRED_ASSETS = ['manifest.json', 'height.f32', 'landcover.u8'];

async function dirSizeBytes(dir: string): Promise<number> {
  let total = 0;
  const entries = await readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      total += await dirSizeBytes(full);
    } else if (entry.isFile()) {
      total += (await stat(full)).size;
    }
  }
  return total;
}

async function readRegion(root: string, name: string): Promise<RegionSummary> {
  const dir = join(root, name);
  const warnings: string[] = [];

  const present = new Set(await readdir(dir));
  for (const required of REQUIRED_ASSETS) {
    if (!present.has(required)) warnings.push(`missing ${required}, this bake is incomplete`);
  }

  let manifest = parseRegionManifest(null);
  if (present.has('manifest.json')) {
    try {
      manifest = parseRegionManifest(JSON.parse(await readFile(join(dir, 'manifest.json'), 'utf8')));
    } catch (err) {
      warnings.push(`manifest.json could not be read: ${(err as Error).message}`);
    }
  }

  let sizeBytes: number | null = null;
  try {
    sizeBytes = await dirSizeBytes(dir);
  } catch {
    warnings.push('could not measure size on disk');
  }

  return {
    name,
    displayName: regionDisplayName(name),
    availability: 'local',
    assetPath: dir,
    home: manifest.home,
    elevationM: manifest.elevationM,
    extentM: manifest.extentM,
    sizeTexels: manifest.sizeTexels,
    metersPerTexel: manifest.metersPerTexel,
    sizeBytes,
    imagery: manifest.imagery,
    attribution: manifest.attribution,
    utmEpsg: manifest.utmEpsg,
    warnings: [...warnings, ...manifest.warnings],
  };
}

/**
 * Phase 1's only `RegionSource`: everything already baked on this machine.
 *
 * It invents nothing. The list is whatever directories exist under the region roots and
 * whatever their manifests say, so a region baked by `tools/bake_region.sh` appears without
 * the launcher being told about it. A hardcoded catalogue would go stale the first time
 * somebody bakes a new place.
 */
export class LocalRegionSource implements RegionSource {
  readonly id = 'local';
  readonly label = 'Baked on this machine';

  /** Populated by `list()`, so `prepare()` reports which root a name came from. */
  private lastErrors: string[] = [];

  constructor(private readonly roots: string[]) {}

  get errors(): string[] {
    return this.lastErrors;
  }

  async list(): Promise<RegionSummary[]> {
    const errors: string[] = [];
    const byName = new Map<string, RegionSummary>();
    let anyRootRead = false;

    for (const root of this.roots) {
      let entries;
      try {
        entries = await readdir(root, { withFileTypes: true });
        anyRootRead = true;
      } catch {
        // A root that does not exist is normal (userData/regions before anything is
        // downloaded), so it is not worth an error line on its own.
        continue;
      }
      for (const entry of entries) {
        if (!entry.isDirectory()) continue;
        // An earlier root wins: precedence is the whole point of the root order.
        if (byName.has(entry.name)) continue;
        try {
          byName.set(entry.name, await readRegion(root, entry.name));
        } catch (err) {
          errors.push(`${entry.name}: ${(err as Error).message}`);
        }
      }
    }

    if (!anyRootRead) {
      errors.push(
        'No region directory found. Point ARDUDECK_REGION_DIR at a directory of baked regions, or set ARDUDECK_GAME_ROOT to the game checkout.',
      );
    }
    this.lastErrors = errors;

    return [...byName.values()].sort((a, b) => a.displayName.localeCompare(b.displayName));
  }

  /** Local regions need no acquisition, so this only re-verifies that they are still there. */
  async prepare(name: string): Promise<PreparedRegion> {
    for (const root of this.roots) {
      const dir = join(root, name);
      try {
        if (!(await stat(dir)).isDirectory()) continue;
      } catch {
        continue;
      }
      const summary = await readRegion(root, name);
      return {
        name,
        assetPath: dir,
        home: summary.home,
        warnings: summary.warnings,
      };
    }
    throw new Error(`Region "${name}" is not present in any region directory`);
  }
}
