import { test, expect } from '@playwright/test';

test.describe('Map interactions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);
  });

  test('map container renders', async ({ page }) => {
    await expect(page.locator('.leaflet-container')).toBeVisible({ timeout: 5000 });
  });

  test('map zoom controls work', async ({ page }) => {
    const map = page.locator('.leaflet-container').first();
    const box = await map.boundingBox();
    if (box) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.wheel(0, -300);
      await page.waitForTimeout(500);
      await page.mouse.wheel(0, 300);
      await page.waitForTimeout(500);
    }
  });

  test('layer toggle button exists', async ({ page }) => {
    const buttons = page.locator('.leaflet-container button, [class*="absolute"] button');
    expect(await buttons.count()).toBeGreaterThan(0);
  });

  test('follow button exists', async ({ page }) => {
    const buttons = page.locator('.leaflet-container ~ div button, .absolute button');
    expect(await buttons.count()).toBeGreaterThan(0);
  });

  test('coordinates display on mouse move', async ({ page }) => {
    const map = page.locator('.leaflet-container').first();
    const box = await map.boundingBox();
    if (box) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.waitForTimeout(500);
      await expect(page.locator('body')).toContainText(/\d+\.\d+/);
    }
  });
});
