import { test, expect } from '@playwright/test';
import { waitForPageLoad, waitForLoadingToComplete, checkDataTestId } from '../utils/test-helpers';

test.describe('Discover Page', () => {
  // Discover page loads data from multiple API endpoints - needs more time
  test.setTimeout(60000);

  test.beforeEach(async ({ page }) => {
    await page.goto('/discover');
    await waitForPageLoad(page);
  });

  test('should display discover page with AI badge', async ({ page }) => {
    await checkDataTestId(page, 'discover-page');

    const title = page.locator('[data-testid="discover-title"]');
    await expect(title).toHaveText('Discover');

    await checkDataTestId(page, 'ai-curated-badge');
  });

  test('should display New Arrivals section', async ({ page }) => {
    await checkDataTestId(page, 'new-arrivals-section');
    await checkDataTestId(page, 'new-arrivals-title');

    await waitForLoadingToComplete(page, 'new-arrivals-loading');

    // Section structure should exist - data may or may not be present depending on backend
    const grid = page.locator('[data-testid="new-arrivals-grid"]');
    const empty = page.locator('[data-testid="new-arrivals-empty"]');

    // At least one of these elements should exist (may not be visible if API errors)
    const gridCount = await grid.count();
    const emptyCount = await empty.count();
    expect(gridCount + emptyCount).toBeGreaterThanOrEqual(1);
  });

  test('should display Celebrity Bottles section', async ({ page }) => {
    await checkDataTestId(page, 'celebrity-section');
    await checkDataTestId(page, 'celebrity-title');

    await waitForLoadingToComplete(page, 'celebrity-loading');

    const grid = page.locator('[data-testid="celebrity-grid"]');
    const empty = page.locator('[data-testid="celebrity-empty"]');

    const gridCount = await grid.count();
    const emptyCount = await empty.count();
    expect(gridCount + emptyCount).toBeGreaterThanOrEqual(1);
  });

  test('should display Early Movers section', async ({ page }) => {
    await checkDataTestId(page, 'early-movers-section');
    await checkDataTestId(page, 'early-movers-title');

    await waitForLoadingToComplete(page, 'early-movers-loading');

    const grid = page.locator('[data-testid="early-movers-grid"]');
    const empty = page.locator('[data-testid="early-movers-empty"]');

    const gridCount = await grid.count();
    const emptyCount = await empty.count();
    expect(gridCount + emptyCount).toBeGreaterThanOrEqual(1);
  });
});
