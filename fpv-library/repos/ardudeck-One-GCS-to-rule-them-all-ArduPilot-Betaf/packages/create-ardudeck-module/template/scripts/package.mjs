#!/usr/bin/env node
/**
 * Build the module and package dist/ into a marketplace-ready zip.
 *
 * Output: <slug>-<version>.zip in the project root.
 *
 * The zip is NOT signed here — the marketplace server signs the bundle
 * when you upload it via the admin review UI. Just drag the zip in.
 */
import { spawn } from 'node:child_process';
import { readFile, rm, stat } from 'node:fs/promises';
import { join } from 'node:path';
import AdmZip from 'adm-zip';

async function run(cmd, args) {
  return new Promise((resolve, reject) => {
    const p = spawn(cmd, args, { stdio: 'inherit' });
    p.on('exit', (code) => (code === 0 ? resolve() : reject(new Error(`${cmd} exited ${code}`))));
    p.on('error', reject);
  });
}

const manifest = JSON.parse(await readFile('module.json', 'utf-8'));
const { slug, version } = manifest;
if (!slug || !version) {
  console.error('module.json missing slug or version');
  process.exit(1);
}

const outZip = `${slug}-${version}.zip`;
await rm(outZip, { force: true });

await run('node', ['esbuild.config.mjs']);

try {
  await stat('dist/module.json');
} catch {
  console.error('Build did not produce dist/module.json');
  process.exit(1);
}

const zip = new AdmZip();
zip.addLocalFolder('dist');
zip.writeZip(outZip);

const { size } = await stat(outZip);
const kb = (size / 1024).toFixed(1);
console.log(`\nPackaged: ${outZip} (${kb} KB)`);
console.log('Upload via the marketplace admin Review tab.');
