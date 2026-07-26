import { app, ipcMain, safeStorage } from 'electron';
import { access, mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { MainHostApi, ModuleManifest } from '@ardudeck/module-sdk';

export function createMainHostApi(manifest: ModuleManifest): MainHostApi {
  const dataDir = join(app.getPath('userData'), 'modules', manifest.slug, 'data');

  // Secrets live in a separate .secret file holding OS-encrypted base64.
  const secretPath = (key: string) => join(dataDir, `${key}.secret`);

  return {
    moduleSlug: manifest.slug,
    dataDir,
    async readData(key) {
      const p = join(dataDir, `${key}.json`);
      try {
        await access(p);
        return await readFile(p, 'utf-8');
      } catch {
        return undefined;
      }
    },
    async writeData(key, value) {
      await mkdir(dataDir, { recursive: true });
      await writeFile(join(dataDir, `${key}.json`), value, 'utf-8');
    },
    async secureRead(key) {
      try {
        await access(secretPath(key));
      } catch {
        return undefined;
      }
      const stored = await readFile(secretPath(key), 'utf-8');
      if (stored.startsWith('plain:')) return stored.slice(6);
      if (!safeStorage.isEncryptionAvailable()) {
        console.warn(`[module:${manifest.slug}] secureRead: OS encryption unavailable, cannot decrypt`);
        return undefined;
      }
      return safeStorage.decryptString(Buffer.from(stored, 'base64'));
    },
    async secureWrite(key, value) {
      await mkdir(dataDir, { recursive: true });
      if (safeStorage.isEncryptionAvailable()) {
        const enc = safeStorage.encryptString(value).toString('base64');
        await writeFile(secretPath(key), enc, 'utf-8');
      } else {
        console.warn(`[module:${manifest.slug}] secureWrite: OS encryption unavailable, storing plaintext`);
        await writeFile(secretPath(key), `plain:${value}`, 'utf-8');
      }
    },
    log(level, ...args) {
      const tag = `[module:${manifest.slug}]`;
      if (level === 'error') console.error(tag, ...args);
      else if (level === 'warn') console.warn(tag, ...args);
      else console.log(tag, ...args);
    },
    onRendererMessage(channel, handler) {
      const fullChannel = `module:${manifest.slug}:${channel}`;
      const listener = async (_: unknown, data: unknown) => handler(data);
      ipcMain.handle(fullChannel, listener);
      return () => ipcMain.removeHandler(fullChannel);
    },
  };
}
