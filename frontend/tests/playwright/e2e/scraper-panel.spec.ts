import { test, expect } from '@playwright/test';
import { waitForPageLoad, checkDataTestId } from '../utils/test-helpers';

test.describe('Scraper Panel Page', () => {
  // Scraper page needs backend connection - give it more time
  test.setTimeout(60000);

  test.beforeEach(async ({ page }) => {
    await page.goto('/scraper');
    // Wait for the page to be visible (may show loading state)
    await page.waitForSelector('[data-testid="scraper-page"]', { timeout: 30000 });
  });

  test('should display scraper page with status badges', async ({ page }) => {
    await checkDataTestId(page, 'scraper-page');
    await checkDataTestId(page, 'scraper-header');

    const title = page.locator('[data-testid="scraper-title"]');
    await expect(title).toContainText('AI Scraper Monitor');

    await checkDataTestId(page, 'connection-status');
    await checkDataTestId(page, 'running-status');
  });

  test('should display scraper controls', async ({ page }) => {
    await checkDataTestId(page, 'scraper-controls');

    // Verify checkboxes
    await checkDataTestId(page, 'tier1-checkbox');
    await checkDataTestId(page, 'tier2-checkbox');
    await checkDataTestId(page, 'parallel-checkbox');

    // Verify action buttons
    await checkDataTestId(page, 'start-scraper-button');
    await checkDataTestId(page, 'clear-logs-button');
    await checkDataTestId(page, 'stream-toggle-button');
  });

  test('should toggle checkbox states', async ({ page }) => {
    const tier1Checkbox = page.locator('[data-testid="tier1-checkbox"]');
    const tier2Checkbox = page.locator('[data-testid="tier2-checkbox"]');

    // Tier1 should be checked by default
    await expect(tier1Checkbox).toBeChecked();
    await expect(tier2Checkbox).not.toBeChecked();

    // Toggle tier2
    await tier2Checkbox.click();
    await expect(tier2Checkbox).toBeChecked();
  });

  test('should display logs container', async ({ page }) => {
    await checkDataTestId(page, 'logs-card');
    await checkDataTestId(page, 'logs-count');
    await checkDataTestId(page, 'logs-container');

    // Should show empty state or log entries
    const emptyState = page.locator('[data-testid="logs-empty"]');
    const logEntries = page.locator('[data-testid^="log-entry-"]');

    const emptyCount = await emptyState.count();
    const entriesCount = await logEntries.count();

    expect(emptyCount + entriesCount).toBeGreaterThan(0);
  });
});
