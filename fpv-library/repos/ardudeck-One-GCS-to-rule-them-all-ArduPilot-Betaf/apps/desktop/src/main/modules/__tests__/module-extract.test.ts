import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mkdtemp, rm, writeFile, readFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import AdmZip from 'adm-zip';
import { extractBundle } from '../module-extract.js';

describe('extractBundle', () => {
  let tmp: string;

  beforeEach(async () => {
    tmp = await mkdtemp(join(tmpdir(), 'mod-extract-'));
  });

  afterEach(async () => {
    await rm(tmp, { recursive: true, force: true });
  });

  it('extracts a zip with module.json to target directory', async () => {
    const zipPath = join(tmp, 'bundle.zip');
    const zip = new AdmZip();
    zip.addFile('module.json', Buffer.from('{"manifestVersion":1}'));
    zip.addFile('renderer.js', Buffer.from('export const x = 1;'));
    zip.writeZip(zipPath);

    const target = join(tmp, 'out');
    await extractBundle(zipPath, target);

    const manifest = await readFile(join(target, 'module.json'), 'utf-8');
    expect(manifest).toContain('manifestVersion');

    const js = await readFile(join(target, 'renderer.js'), 'utf-8');
    expect(js).toContain('export const x');
  });

  it('refuses zip entries with path traversal', async () => {
    const zipPath = join(tmp, 'evil.zip');
    const zip = new AdmZip();
    zip.addFile('placeholder.txt', Buffer.from('pwned'));
    // adm-zip's addFile() sanitizes `..`, so mutate the entry name directly
    // to simulate a hand-crafted malicious zip.
    zip.getEntries()[0]!.entryName = '../../outside.txt';
    zip.writeZip(zipPath);

    const target = join(tmp, 'out');
    await expect(extractBundle(zipPath, target)).rejects.toThrow(/traversal|unsafe/i);
  });

  it('wipes existing target directory before extract', async () => {
    const target = join(tmp, 'out');
    await mkdir(target, { recursive: true });
    await writeFile(join(target, 'stale.txt'), 'old');

    const zipPath = join(tmp, 'bundle.zip');
    const zip = new AdmZip();
    zip.addFile('module.json', Buffer.from('{}'));
    zip.writeZip(zipPath);

    await extractBundle(zipPath, target);
    await expect(readFile(join(target, 'stale.txt'))).rejects.toThrow();
  });

  it('preserves nested directory structure', async () => {
    const zipPath = join(tmp, 'bundle.zip');
    const zip = new AdmZip();
    zip.addFile('module.json', Buffer.from('{}'));
    zip.addFile('assets/icon.png', Buffer.from('fake-png'));
    zip.addFile('src/main/index.js', Buffer.from('// main'));
    zip.writeZip(zipPath);

    const target = join(tmp, 'out');
    await extractBundle(zipPath, target);

    expect((await readFile(join(target, 'assets/icon.png'), 'utf-8'))).toBe('fake-png');
    expect((await readFile(join(target, 'src/main/index.js'), 'utf-8'))).toBe('// main');
  });
});
