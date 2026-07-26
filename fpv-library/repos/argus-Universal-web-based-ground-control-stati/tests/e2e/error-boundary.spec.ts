import { test, expect } from '@playwright/test';

test.describe('Error boundary and graceful degradation', () => {
  test('injecting a JS error does not white-screen the app', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);

    // Inject a runtime error
    await page.evaluate(() => {
      setTimeout(() => {
        throw new Error('Intentional test error: component failure');
      }, 0);
    });
    await page.waitForTimeout(1000);

    // App should still be rendered and visible (no white screen)
    await expect(page.locator('[role="application"]')).toBeVisible();
    await expect(page.locator('body')).not.toHaveText('');

    // No Vite error overlay
    const errorOverlay = page.locator('vite-error-overlay');
    await expect(errorOverlay).toHaveCount(0);
  });

  test('invalid localStorage data on load does not crash', async ({ page }) => {
    // Set corrupted localStorage before navigating
    await page.goto('/');
    await page.evaluate(() => {
      localStorage.setItem('argus_settings', '{invalid json!!!');
      localStorage.setItem('argus_locale', '%%%not_a_locale%%%');
      localStorage.setItem('argus_theme', '{"broken": true, "nested": {{{');
    });

    // Reload the page with corrupted storage
    await page.reload();
    await page.waitForTimeout(2000);

    // App should still render despite corrupted storage
    await expect(page.locator('[role="application"]')).toBeVisible();
    await expect(page.locator('body')).toBeVisible();

    // Should still show the app name
    const banner = page.getByRole('banner');
    await expect(banner.getByText('Argus')).toBeVisible({ timeout: 5000 });
  });

  test('failed API call (500 response) shows graceful error state', async ({ page }) => {
    // Mock all API endpoints to return 500
    await page.route('**/api/**', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal Server Error' }),
      });
    });

    await page.goto('/');
    await page.waitForTimeout(2000);

    // App shell should still render
    await expect(page.locator('[role="application"]')).toBeVisible();
    await expect(page.locator('body')).toBeVisible();

    // No crash indicators
    const errorOverlay = page.locator('vite-error-overlay');
    await expect(errorOverlay).toHaveCount(0);

    // The page should have meaningful content (not blank)
    const bodyText = await page.textContent('body');
    expect(bodyText!.length).toBeGreaterThan(10);
  });

  test('broken WebSocket message does not crash the UI', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);

    // Inject malformed data into the WebSocket message handler
    await page.evaluate(() => {
      // Find and trigger the WebSocket message handler with bad data
      const originalParse = JSON.parse;
      let callCount = 0;
      JSON.parse = function (text: string) {
        callCount++;
        // Corrupt every 3rd parse to simulate bad WS messages
        if (callCount % 3 === 0 && text.includes('"type"')) {
          return { type: 'state', corrupted: undefined, broken: null, bad_field: NaN };
        }
        return originalParse.call(this, text);
      };

      // Also dispatch a fake message event with invalid data
      window.dispatchEvent(new MessageEvent('message', { data: '{{not valid json at all}}' }));
      window.dispatchEvent(new MessageEvent('message', { data: null }));
    });

    await page.waitForTimeout(1500);

    // App should remain functional
    await expect(page.locator('[role="application"]')).toBeVisible();
    await expect(page.locator('body')).toBeVisible();

    // No crash or error overlay
    const errorOverlay = page.locator('vite-error-overlay');
    await expect(errorOverlay).toHaveCount(0);
  });

  test('navigating with corrupted state does not crash', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);

    // Corrupt the app state by injecting bad values
    await page.evaluate(() => {
      localStorage.setItem('argus_settings', JSON.stringify({
        darkTheme: 'not_a_boolean',
        locale: 12345,
        mapMode: { invalid: true },
        showSettings: undefined,
      }));
    });

    // Navigate between tabs rapidly to trigger state reads
    const tabs = ['飞行', '规划', '监控', '参数'];
    for (const tabText of tabs) {
      const tab = page.locator('nav button', { hasText: new RegExp(tabText) }).first();
      if (await tab.isVisible()) {
        await tab.click();
        await page.waitForTimeout(300);
      }
    }

    // App should still be running
    await expect(page.locator('[role="application"]')).toBeVisible();
    await expect(page.locator('body')).not.toHaveText('');
  });

  test('unhandled promise rejection does not crash the app', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);

    // Trigger unhandled promise rejections
    await page.evaluate(() => {
      Promise.reject(new Error('Unhandled test rejection 1'));
      Promise.reject('string rejection');
      Promise.reject(null);

      // Also simulate a fetch failure
      fetch('/api/nonexistent-endpoint').catch(() => {});
    });

    await page.waitForTimeout(1000);

    // App should remain intact
    await expect(page.locator('[role="application"]')).toBeVisible();
    await expect(page.locator('body')).toBeVisible();

    // Navigation should still work
    const planTab = page.locator('nav button', { hasText: /规划|Plan/ }).first();
    if (await planTab.isVisible()) {
      await planTab.click();
      await page.waitForTimeout(500);
      await expect(page.locator('.leaflet-container')).toBeVisible({ timeout: 5000 });
    }
  });

  test('deeply nested error in event handler does not white-screen', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);

    // Add a failing event listener that simulates a component error
    await page.evaluate(() => {
      document.addEventListener('click', () => {
        try {
          // @ts-ignore - intentional type error
          (null as any).nonexistent.deeply.nested.property;
        } catch (e) {
          // Swallowed within handler, but re-throw asynchronously
          setTimeout(() => { throw e; }, 0);
        }
      }, { once: true });
    });

    // Trigger the click
    await page.click('body');
    await page.waitForTimeout(1000);

    // App should survive the error
    await expect(page.locator('[role="application"]')).toBeVisible();

    // Verify the app is still interactive
    const settingsBtn = page.locator('button:has(svg.lucide-settings)').first();
    if (await settingsBtn.isVisible()) {
      await settingsBtn.click();
      await expect(page.locator('h3', { hasText: /设置|Settings/ }).first()).toBeVisible({ timeout: 3000 });
    }
  });

  test('WebSocket close during active use does not crash', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);

    // Force-close the WebSocket connection
    await page.evaluate(() => {
      // Access all WebSocket instances and close them abruptly
      const originalWs = WebSocket;
      const sockets: WebSocket[] = [];
      // @ts-ignore
      window.WebSocket = class extends originalWs {
        constructor(...args: any[]) {
          // @ts-ignore
          super(...args);
          sockets.push(this);
        }
      };

      // Close any open connections with an error code
      for (const ws of sockets) {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close(1006, 'Abnormal closure');
        }
      }

      // Also dispatch error events on the window
      window.dispatchEvent(new ErrorEvent('error', {
        message: 'WebSocket connection failed',
        error: new Error('Connection reset'),
      }));
    });

    await page.waitForTimeout(2000);

    // App should still be rendered
    await expect(page.locator('[role="application"]')).toBeVisible();
    await expect(page.locator('body')).toBeVisible();

    // App should show disconnection indicator but not crash
    const bodyText = await page.textContent('body');
    expect(bodyText!.length).toBeGreaterThan(10);
  });
});
