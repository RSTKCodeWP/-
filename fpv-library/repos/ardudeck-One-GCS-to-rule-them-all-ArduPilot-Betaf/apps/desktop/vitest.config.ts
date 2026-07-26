import { defineConfig, configDefaults } from 'vitest/config';

// Vitest does not pick up electron.vite.config.ts (not a vite.config.* name), so
// it runs with defaults. Those defaults do not exclude `out/`, the gitignored
// electron-vite build output, which contains stale compiled copies of the test
// files. Running them fails (they resolve fixtures/relative paths from the wrong
// root) and is pointless since the source tests already cover the same code.
export default defineConfig({
  test: {
    exclude: [...configDefaults.exclude, '**/out/**'],
  },
});
