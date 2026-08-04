import { mkdir, writeFile, rename } from 'node:fs/promises';
import { dirname } from 'node:path';
import { serializeLaunchConfig, type LaunchConfig } from '../../shared/launch-config.js';

/**
 * Write the config the game boots from.
 *
 * Written to a temp name and renamed into place, because rename is atomic on every platform
 * we ship to: the game must never open a config that is half written. It degrades on a
 * partial file, but degrading is for a config from an older launcher, not for a race we
 * could avoid.
 */
export async function writeLaunchConfig(path: string, config: LaunchConfig): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  const tmp = `${path}.tmp`;
  await writeFile(tmp, serializeLaunchConfig(config), 'utf8');
  await rename(tmp, path);
}
