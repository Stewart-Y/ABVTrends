import { test, expect } from '@playwright/test';
import { waitForPageLoad, waitForLoadingToComplete, checkDataTestId } from '../utils/test-helpers';

test.describe('Dashboard Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForPageLoad(page);
  });

  test('should display dashboard header and title', async ({ page }) => {
    await checkDataTestId(page, 'dashboard-page');
    await checkDataTestId(page, 'dashboard-header');

    const title = page.locator('[data-testid="dashboard-title"]');
    await expect(title).toHaveText('Dashboard');
  });

  test('should display KPI stat cards', async ({ page }) => {
    await waitForLoadingToComplete(page, 'dashboard-loading');

    const kpiGrid = page.locator('[data-testid="kpi-cards-grid"]');
    await expect(kpiGrid).toBeVisible();
  });

  test('should navigate to product detail on trend card click', async ({ page }) => {
    await waitForLoadingToComplete(page, 'dashboard-loading');

    // Wait for viral or trending section to load
    const trendCard = page.locator('[data-testid^="trend-card-"]').first();

    // If no products, skip test
    const cardCount = await trendCard.count();
    if (cardCount === 0) {
      test.skip();
      return;
    }

    await trendCard.click();
    await expect(page).toHaveURL(/\/product\/.+/);
  });

  test('should display sidebar navigation', async ({ page }) => {
    await checkDataTestId(page, 'sidebar');
    await checkDataTestId(page, 'sidebar-nav');

    // Dashboard nav should be visible
    const dashboardNav = page.locator('[data-testid="nav-dashboard"]');
    await expect(dashboardNav).toBeVisible();
  });

  test('should navigate to trends page via sidebar', async ({ page }) => {
    const trendsNav = page.locator('[data-testid="nav-trends"]');
    await trendsNav.click();

    await expect(page).toHaveURL('/trends');
    await checkDataTestId(page, 'trends-page');
  });
});
