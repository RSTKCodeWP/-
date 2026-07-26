import { defineConfig, devices } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

// webServer.cwd defaults to this config file's directory (tests/), where
// `python run.py` exits 2 with "can't open file" — anchor it to the repo
// root explicitly so the command works no matter where npx runs from.
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

export default defineConfig({
  testDir: './e2e',
  timeout: 60000,
  expect: { timeout: 10000 },
  retries: 1,
  workers: 1,
  use: {
    baseURL: 'http://localhost:8100',
    headless: true,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
  outputDir: '../test-results',
  webServer: {
    command: 'ARGUS_NO_BROWSER=1 python run.py --sim',
    cwd: repoRoot,
    url: 'http://localhost:8100/health',
    timeout: 15000,
    reuseExistingServer: true,
  },
});
