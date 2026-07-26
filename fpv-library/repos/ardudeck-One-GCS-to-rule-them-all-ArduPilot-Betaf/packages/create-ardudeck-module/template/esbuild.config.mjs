import { build } from 'esbuild';
import { mkdir, copyFile, writeFile } from 'node:fs/promises';
import { ardudeckModulePlugin } from '@ardudeck/module-sdk/esbuild';

await mkdir('dist', { recursive: true });

// Tell Node the bundled main.js is ESM (no surrounding package.json otherwise).
await writeFile('dist/package.json', JSON.stringify({ type: 'module' }, null, 2));

await build({
  entryPoints: ['src/main/index.ts'],
  bundle: true,
  platform: 'node',
  format: 'esm',
  target: 'node20',
  external: ['electron', 'node-pty'],
  outfile: 'dist/main.js',
});

await build({
  entryPoints: ['src/renderer/index.tsx'],
  bundle: true,
  platform: 'browser',
  format: 'esm',
  target: 'es2022',
  jsx: 'automatic',
  plugins: [ardudeckModulePlugin()],
  outfile: 'dist/renderer.js',
});

await copyFile('module.json', 'dist/module.json');
console.log('Build complete.');
