import { test, expect } from '@playwright/test';
import { connectSimulator, disconnectIfConnected } from './helpers';

test.describe.configure({ mode: 'serial' });

test.describe('Connection flow', () => {
  test.afterEach(async ({ page }) => {
    await disconnectIfConnected(page);
  });

  test('connect to simulator via default port', async ({ page }) => {
    await connectSimulator(page);
    await expect(page.locator('body')).toContainText(
      /Stabilize|Loiter|Guided|Auto|Manual|AltHold|自稳|悬停|引导|自动|手动|定高/,
      { timeout: 10000 },
    );
  });

  test('shows telemetry after connection', async ({ page }) => {
    await connectSimulator(page);
    await expect(page.locator('body')).toContainText(/\d+\.\d+\s*V/, { timeout: 10000 });
  });

  test('disconnect button appears when connected', async ({ page }) => {
    await connectSimulator(page);
    await expect(page.locator('button', { hasText: /^断开$|^Disconnect$/ })).toBeVisible();
  });

  test('disconnect returns to welcome state', async ({ page }) => {
    await connectSimulator(page);
    await page.locator('button', { hasText: /^断开$|^Disconnect$/ }).click();
    await page.waitForTimeout(3000);
    await expect(page.locator('kbd', { hasText: 'Ctrl+K' })).toBeVisible({ timeout: 10000 });
  });
});
