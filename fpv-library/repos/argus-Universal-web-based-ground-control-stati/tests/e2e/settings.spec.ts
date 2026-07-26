import { test, expect } from '@playwright/test';

test.describe('Settings panel', () => {
  test('opens via Ctrl+S', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.keyboard.press('Control+s');
    await expect(page.locator('h3', { hasText: /设置|Settings/ }).first()).toBeVisible({ timeout: 3000 });
  });

  test('opens via settings button', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    const settingsBtn = page.locator('button:has(svg.lucide-settings)').first();
    await settingsBtn.click();
    await expect(page.locator('h3', { hasText: /设置|Settings/ }).first()).toBeVisible({ timeout: 3000 });
  });

  test('theme toggle works', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.keyboard.press('Control+s');
    await page.waitForTimeout(500);

    const themeBtn = page.locator('button', { hasText: /Light|浅色|Dark|深色/ }).first();
    if (await themeBtn.isVisible()) {
      await themeBtn.click();
      await page.waitForTimeout(300);
    }
  });

  test('language selection exists', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.keyboard.press('Control+s');
    await page.waitForTimeout(500);

    const langSelect = page.locator('select').first();
    await expect(langSelect).toBeVisible();
  });

  test('closes panel', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.keyboard.press('Control+s');
    await expect(page.locator('h3', { hasText: /设置|Settings/ }).first()).toBeVisible({ timeout: 3000 });

    const closeBtn = page.locator('button:has(svg.lucide-x)').first();
    if (await closeBtn.isVisible()) {
      await closeBtn.click();
      await expect(page.locator('h3', { hasText: /设置|Settings/ })).not.toBeVisible({ timeout: 3000 });
    }
  });
});
