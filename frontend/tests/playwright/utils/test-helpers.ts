import { Page, expect } from '@playwright/test';

export async function waitForPageLoad(page: Page) {
  await page.waitForLoadState('networkidle');
}

export async function waitForApiResponse(page: Page, urlPattern: string | RegExp) {
  return page.waitForResponse(response =>
    (typeof urlPattern === 'string'
      ? response.url().includes(urlPattern)
      : urlPattern.test(response.url())) &&
    response.status() === 200
  );
}

export async function checkDataTestId(page: Page, testId: string) {
  const element = page.locator(`[data-testid="${testId}"]`);
  await expect(element).toBeVisible();
  return element;
}

export async function waitForLoadingToComplete(page: Page, loadingTestId: string) {
  const loading = page.locator(`[data-testid="${loadingTestId}"]`);
  // Wait for loading to appear then disappear, or not appear at all
  try {
    await loading.waitFor({ state: 'visible', timeout: 2000 });
    await loading.waitFor({ state: 'hidden', timeout: 30000 });
  } catch {
    // Loading may have already completed
  }
}

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
