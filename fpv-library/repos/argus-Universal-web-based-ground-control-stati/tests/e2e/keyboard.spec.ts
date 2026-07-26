import { test, expect } from '@playwright/test';

test.describe('Keyboard shortcuts', () => {
  test('? opens shortcuts panel', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.keyboard.press('Shift+/');
    await expect(page.locator('h2', { hasText: /快捷键|Shortcuts/i })).toBeVisible({ timeout: 3000 });
  });

  test('Escape closes shortcuts panel', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.keyboard.press('Shift+/');
    await expect(page.locator('h2', { hasText: /快捷键|Shortcuts/i })).toBeVisible({ timeout: 3000 });

    await page.keyboard.press('Escape');
    await expect(page.locator('h2', { hasText: /快捷键|Shortcuts/i })).not.toBeVisible({ timeout: 3000 });
  });

  test('L toggles dark/light theme', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await expect(page.locator('html')).toHaveClass(/dark/);
    await page.keyboard.press('l');
    await expect(page.locator('html')).not.toHaveClass(/dark/);
    await page.keyboard.press('l');
    await expect(page.locator('html')).toHaveClass(/dark/);
  });

  test('Ctrl+K opens command palette', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.keyboard.press('Control+k');
    await expect(page.locator('[role="dialog"] input, .fixed input[placeholder]').first()).toBeVisible({ timeout: 3000 });
  });

  test('M toggles map expand', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.keyboard.press('m');
    await page.waitForTimeout(300);
    await page.keyboard.press('m');
    await page.waitForTimeout(300);
  });
});
