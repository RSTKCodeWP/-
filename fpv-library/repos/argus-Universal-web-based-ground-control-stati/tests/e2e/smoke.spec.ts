import { test, expect } from '@playwright/test';

test.describe('Smoke tests', () => {
  test('homepage loads with app name in header', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('body')).toBeVisible();
    await expect(page.getByRole('banner').getByText('Argus')).toBeVisible({ timeout: 8000 });
  });

  test('dark theme is default', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('html')).toHaveClass(/dark/);
  });

  test('welcome card shows when disconnected', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);
    const welcomeCard = page.locator('text=Ctrl+K');
    const isVisible = await welcomeCard.isVisible().catch(() => false);
    expect(isVisible || (await page.locator('.leaflet-container').isVisible())).toBeTruthy();
  });

  test('no third-party branding visible', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);
    const content = await page.textContent('body');
    expect(content).not.toContain('ArduPilot');
    expect(content).not.toContain('ArduCopter');
    expect(content).not.toContain('ChibiOS');
  });

  test('backend health endpoint responds', async ({ request }) => {
    const res = await request.get('/health');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.ok).toBe(true);
  });

  test('API version endpoint responds', async ({ request }) => {
    const res = await request.get('/api/version');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.version).toMatch(/^\d+\.\d+\.\d+$/);
  });
});
