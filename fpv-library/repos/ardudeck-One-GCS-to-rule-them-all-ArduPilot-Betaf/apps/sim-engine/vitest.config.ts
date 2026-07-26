import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';

// Resolve the workspace physics package to its TypeScript source so tests run
// without a prior `tsc` build (dist/ may not exist in a fresh checkout).
export default defineConfig({
  resolve: {
    alias: {
      '@ardudeck/sim-physics': fileURLToPath(
        new URL('../../packages/sim-physics/src/index.ts', import.meta.url),
      ),
    },
  },
});
