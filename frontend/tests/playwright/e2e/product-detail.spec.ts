import { test, expect } from '@playwright/test';
import { waitForPageLoad, waitForLoadingToComplete, checkDataTestId } from '../utils/test-helpers';

test.describe('Product Detail Page', () => {
  test('should display 404 for non-existent product', async ({ page }) => {
    await page.goto('/product/00000000-0000-0000-0000-000000000000');
    await waitForPageLoad(page);

    await checkDataTestId(page, 'product-not-found');

    const returnButton = page.locator('[data-testid="product-not-found"] button');
    await expect(returnButton).toContainText('Return to Dashboard');
  });

  test('should display product detail from dashboard navigation', async ({ page }) => {
    // Start from dashboard
    await page.goto('/');
    await waitForPageLoad(page);
    await waitForLoadingToComplete(page, 'dashboard-loading');

    // Find first product card
    const trendCard = page.locator('[data-testid^="trend-card-"]').first();
    const cardCount = await trendCard.count();

    if (cardCount === 0) {
      test.skip();
      return;
    }

    await trendCard.click();
    await waitForPageLoad(page);
    await waitForLoadingToComplete(page, 'product-loading');

    // Verify product detail elements
    await checkDataTestId(page, 'product-detail-page');
    await checkDataTestId(page, 'back-button');
    await checkDataTestId(page, 'product-name');
  });

  test('should display score gauge and metrics', async ({ page }) => {
    await page.goto('/');
    await waitForPageLoad(page);
    await waitForLoadingToComplete(page, 'dashboard-loading');

    const trendCard = page.locator('[data-testid^="trend-card-"]').first();
    if (await trendCard.count() === 0) {
      test.skip();
      return;
    }

    await trendCard.click();
    await waitForLoadingToComplete(page, 'product-loading');

    // Verify score and metrics
    await checkDataTestId(page, 'score-gauge');
    await checkDataTestId(page, 'signal-count');
    await checkDataTestId(page, 'key-metrics-card');
  });

  test('should navigate back to dashboard', async ({ page }) => {
    await page.goto('/');
    await waitForLoadingToComplete(page, 'dashboard-loading');

    const trendCard = page.locator('[data-testid^="trend-card-"]').first();
    if (await trendCard.count() === 0) {
      test.skip();
      return;
    }

    await trendCard.click();
    await waitForLoadingToComplete(page, 'product-loading');

    const backButton = page.locator('[data-testid="back-button"]');
    await backButton.click();

    await expect(page).toHaveURL('/');
    await checkDataTestId(page, 'dashboard-page');
  });
});
