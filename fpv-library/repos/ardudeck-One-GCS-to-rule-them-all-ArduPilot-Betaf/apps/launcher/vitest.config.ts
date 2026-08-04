import { defineConfig, configDefaults } from 'vitest/config';

// `out/` is the gitignored electron-vite output and holds stale compiled copies of the
// test files; running those duplicates every case. Same exclusion apps/desktop needs.
export default defineConfig({
  test: {
    exclude: [...configDefaults.exclude, '**/out/**'],
  },
});
