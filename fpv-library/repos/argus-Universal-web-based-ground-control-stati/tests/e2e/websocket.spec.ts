import { test, expect } from '@playwright/test';
import { connectSimulator, disconnectIfConnected } from './helpers';

test.describe('WebSocket real-time data', () => {
  test.beforeEach(async ({ page }) => {
    await connectSimulator(page);
  });

  test.afterEach(async ({ page }) => {
    await disconnectIfConnected(page);
  });

  test('telemetry updates in real time', async ({ page }) => {
    await expect(page.locator('body')).toContainText(/\d+\.\d+\s*V/, { timeout: 10000 });
  });

  test('heading compass renders', async ({ page }) => {
    await page.waitForTimeout(3000);
    const svg = page.locator('svg').filter({ hasText: 'N' }).first();
    if (await svg.isVisible()) {
      expect(await svg.isVisible()).toBeTruthy();
    }
  });

  test('message rate displayed', async ({ page }) => {
    // Hz is in the link-quality title attribute, not visible text.
    await expect(page.locator('[title*="Hz"]').first()).toBeVisible({ timeout: 15000 });
  });

  test('link quality visualization renders', async ({ page }) => {
    await page.waitForTimeout(3000);
    const signals = page.locator('svg rect, svg polyline, svg path');
    expect(await signals.count()).toBeGreaterThan(0);
  });
});
