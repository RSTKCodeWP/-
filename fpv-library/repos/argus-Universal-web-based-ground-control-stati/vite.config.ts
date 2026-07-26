import path from 'path';
import { defineConfig } from 'vite';
import { svelte, vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  define: {
    __BUILD_DATE__: JSON.stringify(new Date().toISOString().slice(0, 10)),
  },
  test: {
    include: ['src/**/*.test.ts'],
    coverage: {
      exclude: ['src/lib/fc/px4.ts'],
    },
  },
  build: {
    chunkSizeWarningLimit: 300,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/svelte/')) {
            return 'vendor-svelte';
          }
          if (id.includes('node_modules/clsx') || id.includes('node_modules/tailwind-merge') ||
              id.includes('node_modules/bits-ui') || id.includes('node_modules/@lucide/svelte')) {
            return 'vendor-ui';
          }
          if (id.includes('node_modules/maplibre-gl')) {
            return 'vendor-maplibre';
          }
          if (id.includes('src/lib/mavlink/')) {
            return 'mavlink';
          }
          const toolPaths = ['dflog', 'survey', 'gcj02', 'flightDb', 'plugins', 'units', 'branding'];
          if (toolPaths.some(p => id.includes(`src/lib/${p}`))) {
            return 'tools';
          }
        },
      },
    },
  },
  plugins: [tailwindcss(), svelte({ preprocess: vitePreprocess() })],
  resolve: {
    alias: {
      $lib: path.resolve('./src/lib'),
    },
  },
  server: {
    // Windows + Node >=17 may resolve localhost to ::1, but the backend binds
    // IPv4-only 127.0.0.1 (run.py --host default) — pin both sides to IPv4.
    // LAN debugging still works via `npm run dev -- --host 0.0.0.0`.
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/ws': {
        target: 'ws://127.0.0.1:8100',
        ws: true,
      },
      '/api': {
        target: 'http://127.0.0.1:8100',
      },
      '/health': {
        target: 'http://127.0.0.1:8100',
      },
    },
  },
});
