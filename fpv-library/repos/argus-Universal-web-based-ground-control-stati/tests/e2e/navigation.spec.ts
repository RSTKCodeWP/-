import { test, expect } from '@playwright/test';

test.describe('Tab navigation', () => {
  test('switches to Plan tab', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    const planTab = page.locator('nav button', { hasText: /规划|Plan/ }).first();
    await planTab.click();
    await expect(page.locator('.leaflet-container')).toBeVisible({ timeout: 5000 });
  });

  test('switches to Monitor tab', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    const monitorTab = page.locator('nav button', { hasText: /监控|Monitor/ }).first();
    await monitorTab.click();
    await expect(page.locator('body')).toContainText(/遥控通道|RC Channels|振动|Vibration|导航滤波器|EKF/, { timeout: 5000 });
  });

  test('switches to Params tab', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    const paramsTab = page.locator('nav button', { hasText: /参数|Params/ }).first();
    await paramsTab.click();
    await page.waitForTimeout(500);
    await expect(page.locator('body')).toContainText(/读取|Read|All|全部/i, { timeout: 5000 });
  });

  test('Ctrl+1~4 keyboard shortcuts switch tabs', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.keyboard.press('Control+2');
    await page.waitForTimeout(500);
    await expect(page.locator('.leaflet-container')).toBeVisible({ timeout: 5000 });

    await page.keyboard.press('Control+3');
    await page.waitForTimeout(500);
    await expect(page.locator('body')).toContainText(/遥控通道|RC Channels|振动|Vibration|导航滤波器|EKF/, { timeout: 5000 });

    await page.keyboard.press('Control+1');
    await page.waitForTimeout(500);
    await expect(page.locator('.leaflet-container')).toBeVisible({ timeout: 5000 });
  });
});
