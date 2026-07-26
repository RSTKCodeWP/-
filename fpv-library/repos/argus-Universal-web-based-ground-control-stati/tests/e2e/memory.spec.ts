import { test, expect } from '@playwright/test';
import { connectSimulator } from './helpers';

test.describe('Memory leak detection', () => {
  test.setTimeout(120000);

  // performance.memory is only available in Chromium
  test.skip(({ browserName }) => browserName !== 'chromium', 'performance.memory is Chromium-only');

  test('memory stays bounded during 30s of telemetry streaming', async ({ page }) => {
    await connectSimulator(page);

    // Let the connection stabilize
    await page.waitForTimeout(2000);

    const initialHeap = await page.evaluate(
      () => (performance as any).memory?.usedJSHeapSize ?? 0
    );
    expect(initialHeap).toBeGreaterThan(0);

    // Stream telemetry data for 30 seconds
    await page.waitForTimeout(30000);

    const finalHeap = await page.evaluate(
      () => (performance as any).memory?.usedJSHeapSize ?? 0
    );

    const growthMB = (finalHeap - initialHeap) / (1024 * 1024);
    console.log(`Heap growth during streaming: ${growthMB.toFixed(2)} MB`);

    // Memory growth should be less than 50 MB over 30s of streaming
    expect(growthMB).toBeLessThan(50);
  });

  test('opening and closing panels repeatedly does not leak memory', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    // Force a GC before measuring
    await page.evaluate(() => {
      if ((window as any).gc) (window as any).gc();
    });
    await page.waitForTimeout(500);

    const initialHeap = await page.evaluate(
      () => (performance as any).memory?.usedJSHeapSize ?? 0
    );

    // Open and close panels via command palette (Ctrl+K) multiple times
    const panelNames = ['Inspector', 'Console', 'Log', 'Video', 'Gimbal'];

    for (let cycle = 0; cycle < 5; cycle++) {
      for (const name of panelNames) {
        // Open command palette
        await page.keyboard.press('Control+k');
        await page.waitForTimeout(300);

        // Type panel name and select it
        const input = page.locator('input[placeholder]').first();
        if (await input.isVisible({ timeout: 1000 }).catch(() => false)) {
          await input.fill(name);
          await page.waitForTimeout(200);
          await page.keyboard.press('Enter');
          await page.waitForTimeout(300);
        } else {
          await page.keyboard.press('Escape');
          await page.waitForTimeout(100);
        }
      }

      // Close all panels by pressing Escape multiple times
      for (let i = 0; i < panelNames.length; i++) {
        await page.keyboard.press('Escape');
        await page.waitForTimeout(100);
      }
      await page.waitForTimeout(500);
    }

    // Force GC if available
    await page.evaluate(() => {
      if ((window as any).gc) (window as any).gc();
    });
    await page.waitForTimeout(1000);

    const finalHeap = await page.evaluate(
      () => (performance as any).memory?.usedJSHeapSize ?? 0
    );

    const growthMB = (finalHeap - initialHeap) / (1024 * 1024);
    console.log(`Heap growth after panel open/close cycles: ${growthMB.toFixed(2)} MB`);

    // Panel toggling should not accumulate significant memory
    expect(growthMB).toBeLessThan(50);
  });

  test('rapid tab switching does not accumulate memory', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.evaluate(() => {
      if ((window as any).gc) (window as any).gc();
    });
    await page.waitForTimeout(500);

    const initialHeap = await page.evaluate(
      () => (performance as any).memory?.usedJSHeapSize ?? 0
    );

    // Rapidly switch between tabs 20 times each
    for (let cycle = 0; cycle < 20; cycle++) {
      await page.keyboard.press('Control+1'); // Fly
      await page.waitForTimeout(150);
      await page.keyboard.press('Control+2'); // Plan
      await page.waitForTimeout(150);
      await page.keyboard.press('Control+3'); // Monitor
      await page.waitForTimeout(150);
      await page.keyboard.press('Control+4'); // Params
      await page.waitForTimeout(150);
    }

    await page.evaluate(() => {
      if ((window as any).gc) (window as any).gc();
    });
    await page.waitForTimeout(1000);

    const finalHeap = await page.evaluate(
      () => (performance as any).memory?.usedJSHeapSize ?? 0
    );

    const growthMB = (finalHeap - initialHeap) / (1024 * 1024);
    console.log(`Heap growth after 80 tab switches: ${growthMB.toFixed(2)} MB`);

    // Tab switching should not leak memory significantly
    expect(growthMB).toBeLessThan(50);
  });

  test('connected streaming followed by disconnect does not retain memory', async ({ page }) => {
    await connectSimulator(page);
    await page.waitForTimeout(2000);

    const baselineHeap = await page.evaluate(
      () => (performance as any).memory?.usedJSHeapSize ?? 0
    );

    // Stream for 10 seconds
    await page.waitForTimeout(10000);

    // Disconnect
    const disconnectBtn = page.locator('button', { hasText: /断开|Disconnect/ });
    await disconnectBtn.click();
    await page.waitForTimeout(2000);

    // Force GC
    await page.evaluate(() => {
      if ((window as any).gc) (window as any).gc();
    });
    await page.waitForTimeout(1000);

    const afterDisconnectHeap = await page.evaluate(
      () => (performance as any).memory?.usedJSHeapSize ?? 0
    );

    const growthMB = (afterDisconnectHeap - baselineHeap) / (1024 * 1024);
    console.log(`Heap retained after disconnect: ${growthMB.toFixed(2)} MB`);

    // After disconnecting, memory should not have grown excessively
    expect(growthMB).toBeLessThan(50);
  });

  test('WebSocket reconnection cycles do not leak memory', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    await page.evaluate(() => {
      if ((window as any).gc) (window as any).gc();
    });
    await page.waitForTimeout(500);

    const initialHeap = await page.evaluate(
      () => (performance as any).memory?.usedJSHeapSize ?? 0
    );

    // Connect and disconnect 5 times
    for (let i = 0; i < 5; i++) {
      const portInput = page.locator('input.font-mono').first();
      const currentVal = await portInput.inputValue();
      if (!currentVal.includes('5770')) {
        await portInput.fill('tcp:localhost:5770');
      }

      const connectBtn = page.locator('button', { hasText: /连接|Connect/ }).first();
      await connectBtn.click();
      await expect(page.locator('button', { hasText: /断开|Disconnect/ })).toBeVisible({ timeout: 15000 });

      // Let data stream briefly
      await page.waitForTimeout(3000);

      // Disconnect
      await page.locator('button', { hasText: /断开|Disconnect/ }).click();
      await expect(page.locator('button', { hasText: /连接|Connect/ })).toBeVisible({ timeout: 10000 });
      await page.waitForTimeout(1000);
    }

    await page.evaluate(() => {
      if ((window as any).gc) (window as any).gc();
    });
    await page.waitForTimeout(1000);

    const finalHeap = await page.evaluate(
      () => (performance as any).memory?.usedJSHeapSize ?? 0
    );

    const growthMB = (finalHeap - initialHeap) / (1024 * 1024);
    console.log(`Heap growth after 5 connect/disconnect cycles: ${growthMB.toFixed(2)} MB`);

    expect(growthMB).toBeLessThan(50);
  });
});
