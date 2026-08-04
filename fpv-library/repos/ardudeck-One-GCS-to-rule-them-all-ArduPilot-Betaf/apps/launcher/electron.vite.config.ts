import { resolve } from 'path';
import { defineConfig, externalizeDepsPlugin } from 'electron-vite';
import react from '@vitejs/plugin-react';

// electron-store must be bundled: its `conf` dependency chain is ESM-only and fails
// with ERR_MODULE_NOT_FOUND once packaged. Same exclusion apps/desktop needs.
export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin({ exclude: ['electron-store'] })],
    build: {
      rollupOptions: {
        input: { index: resolve(__dirname, 'src/main/index.ts') },
      },
    },
  },
  preload: {
    plugins: [externalizeDepsPlugin({ exclude: ['electron-store'] })],
    build: {
      rollupOptions: {
        input: { index: resolve(__dirname, 'src/main/preload.ts') },
      },
    },
  },
  renderer: {
    root: 'src/renderer',
    build: {
      target: 'esnext',
      rollupOptions: {
        input: { index: resolve(__dirname, 'src/renderer/index.html') },
      },
    },
    optimizeDeps: {
      esbuildOptions: { target: 'esnext' },
    },
    plugins: [react()],
  },
});
