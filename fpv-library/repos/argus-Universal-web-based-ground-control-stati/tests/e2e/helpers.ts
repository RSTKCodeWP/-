import { expect, type Page } from '@playwright/test';

export async function connectSimulator(page: Page) {
  await page.goto('/');
  await page.waitForTimeout(1500);

  // Idempotent: the backend link is global, so a prior test (or spec) that
  // failed before its cleanup leaves the UI connected — in that state the
  // port input doesn't render and fill() would burn the whole test timeout.
  const disconnectBtn = page.locator('button', { hasText: /^断开$|^Disconnect$/ });
  if (await disconnectBtn.isVisible({ timeout: 500 }).catch(() => false)) {
    return;
  }

  const portInput = page.locator('input.port-input').first();
  await portInput.fill('tcp:localhost:5770');
  await page.waitForTimeout(300);

  const connectBtn = page.locator('button', { hasText: /^连接$|^Connect$/ }).first();
  await connectBtn.click();

  await expect(page.locator('button', { hasText: /^断开$|^Disconnect$/ })).toBeVisible({ timeout: 15000 });
  // Wait for actual telemetry, not just the Disconnect button: the backend
  // link is global and shared across every spec, so on a busy CI run the
  // heartbeat can lag the button by seconds. Downstream steps (param fetch,
  // mode buttons) silently no-op against a not-yet-live link — the voltage
  // readout in the StatusBar is the first proof the sim is actually pushing.
  await expect(page.locator('body')).toContainText(/\d+\.\d+\s*V/, { timeout: 15000 });
}

export async function disconnectIfConnected(page: Page) {
  const disconnectBtn = page.locator('button', { hasText: /^断开$|^Disconnect$/ });
  if (await disconnectBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
    await disconnectBtn.click();
    await page.waitForTimeout(2000);
  }
}
