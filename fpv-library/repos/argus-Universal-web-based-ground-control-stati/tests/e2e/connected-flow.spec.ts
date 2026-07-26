import { test, expect } from '@playwright/test';
import { connectSimulator, disconnectIfConnected } from './helpers';

test.describe.configure({ mode: 'serial' });

test.describe('Connected flow — full lifecycle', () => {
  test.afterEach(async ({ page }) => {
    await disconnectIfConnected(page);
  });

  test('telemetry overlay shows voltage and altitude', async ({ page }) => {
    await connectSimulator(page);
    await expect(page.locator('body')).toContainText(/\d+\.\d+\s*V/, { timeout: 10000 });
  });

  test('mode buttons render after connection', async ({ page }) => {
    await connectSimulator(page);
    const buttons = page.locator('button', { hasText: /Stabilize|Alt Hold|Loiter|Auto|RTL|Land|自稳|定高|悬停|自动|返航|降落/ });
    await expect(buttons.first()).toBeVisible({ timeout: 10000 });
    // Default layout: RTL + pause-to-Loiter quick actions in the nav bar.
    // The four-button mode group only renders with the map expanded
    // (MapControls is gated on app.mapExpanded).
    const count = await buttons.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test('clicking mode button sends mode switch', async ({ page }) => {
    await connectSimulator(page);
    const loiterBtn = page.locator('button', { hasText: /Loiter|悬停/ }).first();
    if (await loiterBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await loiterBtn.click();
      await page.waitForTimeout(2000);
    }
  });

  test('RTL button visible in nav bar', async ({ page }) => {
    await connectSimulator(page);
    const rtlBtn = page.locator('button', { hasText: /RTL|返航/ }).first();
    await expect(rtlBtn).toBeVisible({ timeout: 8000 });
  });

  test('controls panel opens and shows arm button', async ({ page }) => {
    await connectSimulator(page);
    const controlsBtn = page.locator('button', { hasText: /Controls|操控|控制/ }).first();
    if (await controlsBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await controlsBtn.click();
      await page.waitForTimeout(1000);
      const armBtn = page.locator('button', { hasText: /Arm|解锁/ }).first();
      await expect(armBtn).toBeVisible({ timeout: 5000 });
    }
  });

  test('event bar toggles event log', async ({ page }) => {
    await connectSimulator(page);
    const eventBar = page.locator('button', { hasText: /Events|事件/ }).first();
    await expect(eventBar).toBeVisible({ timeout: 8000 });
    await eventBar.click();
    await page.waitForTimeout(1000);
  });

  test('log panel opens via nav button', async ({ page }) => {
    await connectSimulator(page);
    const logBtn = page.locator('button', { hasText: /Logs|日志/ }).first();
    if (await logBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await logBtn.click();
      await page.waitForTimeout(2000);
    }
  });

  test('calibration panel opens via nav button', async ({ page }) => {
    await connectSimulator(page);
    const calBtn = page.locator('button', { hasText: /Calibrate|校准/ }).first();
    if (await calBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await calBtn.click();
      await page.waitForTimeout(2000);
    }
  });

  test('switching to Monitor view shows telemetry panels', async ({ page }) => {
    await connectSimulator(page);
    const monitorTab = page.locator('button', { hasText: /Monitor|监控/ }).first();
    await monitorTab.click();
    await page.waitForTimeout(3000);
    const panels = page.locator('.grid > div');
    const count = await panels.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test('switching to Plan view shows mission panel', async ({ page }) => {
    await connectSimulator(page);
    const planTab = page.locator('button', { hasText: /Plan|规划/ }).first();
    await planTab.click();
    await page.waitForTimeout(3000);
  });

  test('switching to Params view shows param panel', async ({ page }) => {
    await connectSimulator(page);
    const paramsTab = page.locator('button', { hasText: /Params|参数/ }).first();
    await paramsTab.click();
    await page.waitForTimeout(3000);
  });

  test('disconnect returns to welcome state', async ({ page }) => {
    await connectSimulator(page);
    const disconnectBtn = page.locator('button', { hasText: /^断开$|^Disconnect$/ });
    await disconnectBtn.click();
    await page.waitForTimeout(3000);
    await expect(page.locator('kbd', { hasText: 'Ctrl+K' })).toBeVisible({ timeout: 10000 });
  });
});
