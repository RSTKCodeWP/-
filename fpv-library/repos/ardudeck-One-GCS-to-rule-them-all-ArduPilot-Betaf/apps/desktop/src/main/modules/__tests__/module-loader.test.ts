import { describe, it, expect, vi } from 'vitest';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { loadModuleMain } from '../module-loader.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE = join(__dirname, 'fixtures/test-module');

describe('loadModuleMain', () => {
  it('loads main entry and calls activate with host api', async () => {
    const logSpy = vi.fn();
    const host = {
      moduleSlug: 'test.fixture.minimal',
      dataDir: '/tmp/x',
      readData: async () => undefined,
      writeData: async () => {},
      secureRead: async () => undefined,
      secureWrite: async () => {},
      log: logSpy,
      onRendererMessage: () => () => {},
    };
    const result = await loadModuleMain(FIXTURE, 'main.js', host);
    expect(logSpy).toHaveBeenCalledWith('info', 'activated', 'test.fixture.minimal');
    expect(result).toEqual({ activated: true });
  });

  it('throws if main file does not exist', async () => {
    const host = {
      moduleSlug: 'x',
      dataDir: '/tmp/x',
      readData: async () => undefined,
      writeData: async () => {},
      secureRead: async () => undefined,
      secureWrite: async () => {},
      log: () => {},
      onRendererMessage: () => () => {},
    };
    await expect(loadModuleMain(FIXTURE, 'nope.js', host)).rejects.toThrow();
  });
});
