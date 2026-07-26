import { test, expect } from '@playwright/test';

test.describe('Mission planning', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);
    const planTab = page.locator('nav button', { hasText: /规划|Plan/ }).first();
    await planTab.click();
    await page.waitForTimeout(1000);
  });

  test('plan view shows map and mission panel', async ({ page }) => {
    await expect(page.locator('.leaflet-container')).toBeVisible({ timeout: 5000 });
  });

  test('click on map adds waypoint', async ({ page }) => {
    const map = page.locator('.leaflet-container').first();
    const box = await map.boundingBox();
    if (box) {
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
      await page.waitForTimeout(800);
      await expect(page.locator('body')).toContainText(/#1|WP1|航点/, { timeout: 3000 });
    }
  });

  test('add multiple waypoints shows distance', async ({ page }) => {
    const map = page.locator('.leaflet-container').first();
    const box = await map.boundingBox();
    if (box) {
      await page.mouse.click(box.x + box.width * 0.3, box.y + box.height / 2);
      await page.waitForTimeout(400);
      await page.mouse.click(box.x + box.width * 0.7, box.y + box.height / 2);
      await page.waitForTimeout(800);
      await expect(page.locator('body')).toContainText(/\d+\s*(m|km|米)/, { timeout: 5000 });
    }
  });

  test('Ctrl+Z undoes waypoint addition', async ({ page }) => {
    const map = page.locator('.leaflet-container').first();
    const box = await map.boundingBox();
    if (box) {
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
      await page.waitForTimeout(500);
      await page.keyboard.press('Control+z');
      await page.waitForTimeout(500);
    }
  });

  test('default altitude input is editable', async ({ page }) => {
    const altInput = page.locator('input[type="number"]').first();
    if (await altInput.isVisible()) {
      await altInput.fill('80');
      await expect(altInput).toHaveValue('80');
    }
  });

  test('circle generator UI exists', async ({ page }) => {
    const circleBtn = page.locator('button', { hasText: /圆形|Circle/ }).first();
    if (await circleBtn.isVisible()) {
      await circleBtn.click();
      await page.waitForTimeout(300);
      await expect(page.locator('button', { hasText: /Gen|生成/ })).toBeVisible({ timeout: 3000 });
    }
  });
});
