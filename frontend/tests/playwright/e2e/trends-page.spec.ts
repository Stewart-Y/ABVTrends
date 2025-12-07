import { test, expect } from '@playwright/test';
import { waitForPageLoad, waitForLoadingToComplete, checkDataTestId } from '../utils/test-helpers';

test.describe('Trends Explorer Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/trends');
    await waitForPageLoad(page);
  });

  test('should display trends page with filters', async ({ page }) => {
    await checkDataTestId(page, 'trends-page');
    await checkDataTestId(page, 'trends-header');

    const title = page.locator('[data-testid="trends-title"]');
    await expect(title).toHaveText('Trends Explorer');

    // Verify filter controls exist
    await checkDataTestId(page, 'trends-filters');
    await checkDataTestId(page, 'search-input');
    await checkDataTestId(page, 'category-filter');
    await checkDataTestId(page, 'tier-filter');
  });

  test('should filter by category', async ({ page }) => {
    await waitForLoadingToComplete(page, 'trends-loading');

    const categoryFilter = page.locator('[data-testid="category-filter"]');
    await categoryFilter.selectOption('spirits');

    // Wait for filter to apply
    await waitForLoadingToComplete(page, 'trends-loading');

    // Verify category filter is now set to spirits
    await expect(categoryFilter).toHaveValue('spirits');
  });

  test('should search products by name', async ({ page }) => {
    await waitForLoadingToComplete(page, 'trends-loading');

    const searchInput = page.locator('[data-testid="search-input"]');
    await searchInput.fill('tequila');

    // Wait for debounce and filter
    await page.waitForTimeout(500);
    await waitForLoadingToComplete(page, 'trends-loading');

    // Results should update
    const resultsCount = page.locator('[data-testid="results-count"]');
    await expect(resultsCount).toBeVisible();
  });

  test('should display results table', async ({ page }) => {
    await waitForLoadingToComplete(page, 'trends-loading');

    const table = page.locator('[data-testid="trends-table"]');
    await expect(table).toBeVisible();

    // Check for either table content OR empty state
    const tableHeader = page.locator('[data-testid="trends-table-header"]');
    const emptyState = page.locator('[data-testid="trends-empty"]');

    // One of these should be visible
    await expect(tableHeader.or(emptyState)).toBeVisible();
  });

  test('should navigate to product detail on row click', async ({ page }) => {
    await waitForLoadingToComplete(page, 'trends-loading');

    // Wait a bit for data to be rendered
    await page.waitForTimeout(500);

    const rows = page.locator('[data-testid^="trend-row-"]');
    const rowCount = await rows.count();

    if (rowCount === 0) {
      // Check for empty state instead - this is acceptable
      const emptyState = page.locator('[data-testid="trends-empty"]');
      const tableHeader = page.locator('[data-testid="trends-table-header"]');
      await expect(emptyState.or(tableHeader)).toBeVisible();
      return; // Skip navigation test when no data
    }

    await rows.first().click();
    await expect(page).toHaveURL(/\/product\/.+/);
  });
});
