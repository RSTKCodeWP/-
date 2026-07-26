import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
import { access } from 'node:fs/promises';
import type { MainHostApi, ModuleMainExports } from '@ardudeck/module-sdk';

export async function loadModuleMain(
  installPath: string,
  entryRelative: string,
  host: MainHostApi,
): Promise<unknown> {
  const full = join(installPath, entryRelative);
  await access(full);
  const url = pathToFileURL(full).href;
  const mod = (await import(url)) as ModuleMainExports;
  if (typeof mod.activate !== 'function') {
    return undefined;
  }
  return mod.activate(host);
}
