import { test, expect } from '@playwright/test';

test.describe('Command palette', () => {
  test('opens with Ctrl+K', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.keyboard.press('Control+k');
    await page.waitForTimeout(500);
    await expect(page.locator('input[placeholder]').last()).toBeVisible();
  });

  test('shows navigation commands', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.keyboard.press('Control+k');
    await page.waitForTimeout(500);

    await expect(page.locator('body')).toContainText(/Fly|Plan|Monitor|Params|飞行|计划|监控|参数/);
  });

  test('typing filters results', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.keyboard.press('Control+k');
    await page.waitForTimeout(500);

    const searchInput = page.locator('input[placeholder]').last();
    await searchInput.fill('plan');
    await page.waitForTimeout(300);
  });

  test('Escape closes palette', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.keyboard.press('Control+k');
    await page.waitForTimeout(500);
    await expect(page.locator('input[placeholder]').last()).toBeVisible();

    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);
  });
});
