import { join, resolve } from 'node:path';

/** Injected so these resolvers stay pure and unit-testable without a real filesystem. */
export type ExistsFn = (path: string) => boolean;

export interface GameRootOptions {
  /** `ARDUDECK_GAME_ROOT`, the escape hatch for a checkout in an unusual place. */
  envGameRoot?: string | undefined;
  /** `process.resourcesPath` when packaged. */
  resourcesPath?: string | undefined;
  /** The launcher package directory, used to walk out to the monorepo in dev. */
  appDir: string;
  isPackaged: boolean;
  exists: ExistsFn;
}

/**
 * A game root is the directory holding `godot/`, so either the game repo checkout in dev or
 * the staged game payload beside a packaged launcher. Returns every candidate that exists,
 * most specific first, because a machine can legitimately have both.
 */
export function findGameRoots(opts: GameRootOptions): string[] {
  const candidates: string[] = [];
  if (opts.envGameRoot) candidates.push(resolve(opts.envGameRoot));
  if (opts.isPackaged && opts.resourcesPath) {
    candidates.push(join(opts.resourcesPath, 'game'));
  }
  // apps/launcher -> apps -> monorepo root -> sibling checkout.
  const monorepoRoot = resolve(opts.appDir, '..', '..');
  candidates.push(resolve(monorepoRoot, '..', 'ardudeck-game'));
  candidates.push(join(monorepoRoot, 'game'));

  const seen = new Set<string>();
  return candidates.filter((c) => {
    if (seen.has(c)) return false;
    seen.add(c);
    return opts.exists(join(c, 'godot'));
  });
}

export interface RegionRootOptions {
  /** `ARDUDECK_REGION_DIR`, a single directory of baked regions. */
  envRegionDir?: string | undefined;
  gameRoots: string[];
  /** Electron userData. Where downloaded or user-baked regions will land later. */
  userDataDir: string;
}

/**
 * Directories scanned for baked regions, in precedence order. A region name found in an
 * earlier root shadows the same name in a later one, so an explicitly pointed-at directory
 * always wins over whatever shipped.
 */
export function buildRegionRoots(opts: RegionRootOptions): string[] {
  const roots: string[] = [];
  if (opts.envRegionDir) roots.push(resolve(opts.envRegionDir));
  for (const root of opts.gameRoots) {
    roots.push(join(root, 'godot', 'assets', 'terrain'));
  }
  roots.push(join(opts.userDataDir, 'regions'));

  const seen = new Set<string>();
  return roots.filter((r) => {
    if (seen.has(r)) return false;
    seen.add(r);
    return true;
  });
}
