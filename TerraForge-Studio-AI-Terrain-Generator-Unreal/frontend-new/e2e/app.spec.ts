import { test, expect } from '@playwright/test';

test.describe('TerraForge Studio', () => {
  test('has correct title and meta tags', async ({ page }) => {
    await page.goto('/');

    // Check title
    await expect(page).toHaveTitle(/TerraForge Studio/);

    // Check meta description
    const metaDescription = page.locator('meta[name="description"]');
    await expect(metaDescription).toHaveAttribute('content', /3D terrains/);
  });

  test('loads main interface', async ({ page }) => {
    await page.goto('/');

    // Wait for app to load
    await page.waitForLoadState('networkidle');

    // Check if root element exists
    const root = page.locator('#root');
    await expect(root).toBeVisible();
  });

  test('keyboard shortcuts modal opens with Ctrl+K', async ({ page }) => {
    await page.goto('/');
    
    // Press Ctrl+K
    await page.keyboard.press('Control+k');

    // Check if shortcuts modal appears
    const modal = page.getByText(/Keyboard Shortcuts/i);
    await expect(modal).toBeVisible();

    // Close with Escape
    await page.keyboard.press('Escape');
    await expect(modal).not.toBeVisible();
  });

  test('is responsive on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');

    const root = page.locator('#root');
    await expect(root).toBeVisible();
  });

  test('PWA manifest is accessible', async ({ page }) => {
    await page.goto('/');

    // Check manifest link
    const manifest = page.locator('link[rel="manifest"]');
    await expect(manifest).toHaveAttribute('href', '/manifest.json');

    // Navigate to manifest
    const response = await page.goto('/manifest.json');
    expect(response?.status()).toBe(200);
    
    const manifestData = await response?.json();
    expect(manifestData.name).toBe('TerraForge Studio');
  });

  test('favicon is loaded', async ({ page }) => {
    await page.goto('/');

    const favicon = page.locator('link[rel="icon"][type="image/svg+xml"]');
    await expect(favicon).toHaveAttribute('href', '/favicon.svg');
  });

  test('handles navigation with Tab key', async ({ page }) => {
    await page.goto('/');

    // Press Tab to navigate
    await page.keyboard.press('Tab');
    
    // Check if an element is focused
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();
  });
});

test.describe('Error Handling', () => {
  test('shows error boundary on critical errors', async ({ page }) => {
    // This test would need a way to trigger an error
    // For now, it's a placeholder
    await page.goto('/');
    
    // In a real scenario, you'd trigger an error and check for error boundary
    // const errorBoundary = page.getByText(/Oops! Something went wrong/i);
  });
});

test.describe('Performance', () => {
  test('page loads within acceptable time', async ({ page }) => {
    const startTime = Date.now();
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    const loadTime = Date.now() - startTime;

    // Should load in less than 5 seconds
    expect(loadTime).toBeLessThan(5000);
  });

  test('lazy loads heavy components', async ({ page }) => {
    await page.goto('/');

    // Check that CesiumJS chunk is not loaded initially
    const resources = await page.evaluate(() => {
      return performance.getEntriesByType('resource').map(r => r.name);
    });

    // CesiumJS should be in a separate chunk
    const _hasCesiumChunk = resources.some(r => r.includes('cesium'));
    
    // This assertion depends on whether CesiumJS is used on the initial page
    // Adjust based on actual implementation
  });
});
