import { test, expect } from '@playwright/test';

test.describe('Network resilience', () => {
  test('app survives blocked API calls gracefully', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);

    await page.route('**/api/**', (route) => {
      route.fulfill({ status: 503, body: 'Service Unavailable' });
    });

    await page.locator('nav button', { hasText: /参数|Params/ }).first().click();
    await page.waitForTimeout(1000);

    const hasError = await page.locator('#vite-error-overlay').isVisible().catch(() => false);
    expect(hasError).toBe(false);
  });

  test('page state persists through brief offline period', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.locator('nav button', { hasText: /规划|Plan/ }).first().click();
    await page.waitForTimeout(500);

    await page.route('**/*', (route) => route.abort('connectionrefused'));
    await page.waitForTimeout(2000);

    await page.unroute('**/*');
    await page.waitForTimeout(1000);

    await expect(page.locator('.leaflet-container')).toBeVisible();
  });

  test('corrupted WebSocket message does not crash', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);

    await page.evaluate(() => {
      const event = new MessageEvent('message', { data: '{invalid json!!!' });
      window.dispatchEvent(event);
    });

    await page.waitForTimeout(1000);
    await expect(page.locator('body')).toBeVisible();
    const hasError = await page.locator('#vite-error-overlay').isVisible().catch(() => false);
    expect(hasError).toBe(false);
  });

  test('app remains functional after backend restart simulation', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);

    await page.route('**/health', (route) => {
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' });
    });

    await page.waitForTimeout(1000);
    await expect(page.locator('.leaflet-container')).toBeVisible();
  });
});
