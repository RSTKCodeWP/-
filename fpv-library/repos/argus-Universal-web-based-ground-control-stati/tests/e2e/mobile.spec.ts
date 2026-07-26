import { test, expect } from '@playwright/test';

test.describe('Mobile responsive layout', () => {
  test.use({ viewport: { width: 375, height: 667 } });

  test('bottom navigation bar appears on mobile viewport', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);

    const bottomNav = page.locator('nav.md\\:hidden');
    await expect(bottomNav).toBeVisible({ timeout: 5000 });

    // Verify it contains the 4 tab buttons
    const buttons = bottomNav.locator('button');
    await expect(buttons).toHaveCount(4);
  });

  test('top navigation tabs are hidden on mobile', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);

    // The desktop nav has the class max-md:hidden
    const topNav = page.locator('nav.max-md\\:hidden');
    await expect(topNav).not.toBeVisible();
  });

  test('bottom nav Fly tab is active by default', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);

    const bottomNav = page.locator('nav.md\\:hidden');
    const flyButton = bottomNav.locator('button', { hasText: /飞行|Fly/ }).first();
    await expect(flyButton).toBeVisible();
    await expect(flyButton).toHaveClass(/text-primary/);
  });

  test('bottom nav Plan tab switches view', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);

    const bottomNav = page.locator('nav.md\\:hidden');
    const planTab = bottomNav.locator('button', { hasText: /规划|Plan/ }).first();
    await planTab.click();
    await page.waitForTimeout(500);

    await expect(planTab).toHaveClass(/text-primary/);
    await expect(page.locator('.leaflet-container')).toBeVisible({ timeout: 5000 });
  });

  test('bottom nav Monitor tab switches view', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);

    const bottomNav = page.locator('nav.md\\:hidden');
    const monitorTab = bottomNav.locator('button', { hasText: /监控|Monitor/ }).first();
    await monitorTab.click();
    await page.waitForTimeout(500);

    await expect(monitorTab).toHaveClass(/text-primary/);
    await expect(page.locator('body')).toContainText(/遥控通道|RC Channels|振动|Vibration|导航滤波器|EKF/, { timeout: 5000 });
  });

  test('bottom nav Params tab switches view', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);

    const bottomNav = page.locator('nav.md\\:hidden');
    const paramsTab = bottomNav.locator('button', { hasText: /参数|Params/ }).first();
    await paramsTab.click();
    await page.waitForTimeout(500);

    await expect(paramsTab).toHaveClass(/text-primary/);
    await expect(page.locator('body')).toContainText(/读取|Read|All|全部/i, { timeout: 5000 });
  });

  test('map fills the screen on mobile', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);

    const mapContainer = page.locator('.leaflet-container').first();
    await expect(mapContainer).toBeVisible({ timeout: 5000 });

    const box = await mapContainer.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      // Map should be at least 80% of viewport width
      expect(box.width).toBeGreaterThan(375 * 0.8);
      // Map should occupy significant vertical space
      expect(box.height).toBeGreaterThan(667 * 0.4);
    }
  });

  test('settings panel is accessible on mobile', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);

    // Open settings via keyboard shortcut
    await page.keyboard.press('Control+s');
    await page.waitForTimeout(500);

    const settingsHeader = page.locator('h3', { hasText: /设置|Settings/ }).first();
    await expect(settingsHeader).toBeVisible({ timeout: 3000 });

    // Settings panel should be visible and usable within the mobile viewport
    const settingsPanel = settingsHeader.locator('..').locator('..');
    await expect(settingsPanel).toBeVisible();
  });

  test('mission panel is scrollable on small screen', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);

    // Navigate to Plan tab
    const bottomNav = page.locator('nav.md\\:hidden');
    const planTab = bottomNav.locator('button', { hasText: /规划|Plan/ }).first();
    await planTab.click();
    await page.waitForTimeout(1000);

    // The plan view container should have overflow-auto to be scrollable
    const planContainer = page.locator('.flex-1.flex.flex-col.overflow-auto');
    await expect(planContainer).toBeVisible({ timeout: 5000 });

    // Verify the page is scrollable by checking overflow properties
    const isScrollable = await page.evaluate(() => {
      const el = document.querySelector('.flex-1.flex.flex-col.overflow-auto');
      if (!el) return false;
      const style = window.getComputedStyle(el);
      return style.overflowY === 'auto' || style.overflow === 'auto';
    });
    expect(isScrollable).toBe(true);
  });
});
