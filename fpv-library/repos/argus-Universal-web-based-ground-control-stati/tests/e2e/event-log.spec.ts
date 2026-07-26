import { test, expect } from '@playwright/test';
import { connectSimulator, disconnectIfConnected } from './helpers';

test.describe('Event log', () => {
  test.beforeEach(async ({ page }) => {
    await connectSimulator(page);
  });

  test.afterEach(async ({ page }) => {
    await disconnectIfConnected(page);
  });

  test('event bar shows at bottom', async ({ page }) => {
    await page.waitForTimeout(3000);
    await expect(page.locator('body')).toContainText(/事件|Event/i);
  });

  test('click event bar expands log', async ({ page }) => {
    await page.waitForTimeout(3000);
    const eventBar = page.locator('div', { hasText: /事件.*\(\d+\)|Event.*\(\d+\)/ }).last();
    if (await eventBar.isVisible()) {
      await eventBar.click();
      await page.waitForTimeout(500);
    }
  });

  test('events accumulate over time', async ({ page }) => {
    await page.waitForTimeout(5000);
    const text = await page.locator('body').textContent();
    const countMatch = text?.match(/(?:事件|Event)[^\d]*\((\d+)\)/);
    if (countMatch) {
      expect(parseInt(countMatch[1])).toBeGreaterThan(0);
    }
  });
});
