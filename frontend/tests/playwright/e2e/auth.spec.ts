import { test, expect } from '@playwright/test';
import { waitForPageLoad, checkDataTestId, API_BASE } from '../utils/test-helpers';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page, context }) => {
    // Clear localStorage before each test
    await context.clearCookies();
    await page.goto('/login');
    await page.evaluate(() => localStorage.clear());
  });

  test.describe('Login Page', () => {
    test('should display login form', async ({ page }) => {
      await waitForPageLoad(page);

      // Check for logo (use first match to avoid multiple element issues)
      await expect(page.locator('h1:text("ABVTrends")').first()).toBeVisible();

      // Check for form elements
      await expect(page.locator('input[type="email"]')).toBeVisible();
      await expect(page.locator('input[type="password"]')).toBeVisible();
      await expect(page.locator('button[type="submit"]')).toBeVisible();

      // Check for register link
      await expect(page.getByText('Create one')).toBeVisible();
    });

    test('should show error on invalid credentials', async ({ page }) => {
      await waitForPageLoad(page);

      // Fill in invalid credentials
      await page.fill('input[type="email"]', 'invalid@example.com');
      await page.fill('input[type="password"]', 'wrongpassword');

      // Submit form
      await page.click('button[type="submit"]');

      // Wait for error message
      await expect(page.locator('text=Invalid email or password')).toBeVisible({
        timeout: 10000,
      });
    });

    test('should login successfully with valid credentials', async ({ page }) => {
      await waitForPageLoad(page);

      // Fill in valid credentials
      await page.fill('input[type="email"]', 'admin@abvtrends.com');
      await page.fill('input[type="password"]', 'ABVTrendsAdmin2024!');

      // Submit form
      await page.click('button[type="submit"]');

      // Should redirect to dashboard
      await expect(page).toHaveURL('/', { timeout: 10000 });

      // Check localStorage for token
      const token = await page.evaluate(() => localStorage.getItem('abvtrends_token'));
      expect(token).toBeTruthy();
    });

    test('should navigate to register page', async ({ page }) => {
      await waitForPageLoad(page);

      await page.click('text=Create one');

      await expect(page).toHaveURL('/register');
    });

    test('should show loading state during login', async ({ page }) => {
      await waitForPageLoad(page);

      await page.fill('input[type="email"]', 'admin@abvtrends.com');
      await page.fill('input[type="password"]', 'ABVTrendsAdmin2024!');

      // Click and immediately check for loading state
      const submitButton = page.locator('button[type="submit"]');
      await submitButton.click();

      // Button should show loading text
      await expect(submitButton).toContainText(/Signing in/);
    });

    test('should redirect authenticated users to dashboard', async ({ page }) => {
      // First, login
      await page.fill('input[type="email"]', 'admin@abvtrends.com');
      await page.fill('input[type="password"]', 'ABVTrendsAdmin2024!');
      await page.click('button[type="submit"]');

      // Wait for redirect
      await expect(page).toHaveURL('/', { timeout: 10000 });
      await waitForPageLoad(page);

      // Try to go back to login
      await page.goto('/login');

      // Should redirect back to dashboard
      await expect(page).toHaveURL('/', { timeout: 10000 });
    });
  });

  test.describe('Register Page', () => {
    test('should display registration form', async ({ page }) => {
      await page.goto('/register');
      await waitForPageLoad(page);

      // Check for form elements
      await expect(page.locator('input[type="email"]')).toBeVisible();
      await expect(page.locator('input#password')).toBeVisible();
      await expect(page.locator('input#confirmPassword')).toBeVisible();
      await expect(page.locator('button[type="submit"]')).toBeVisible();

      // Check for login link
      await expect(page.locator('text=Sign in')).toBeVisible();
    });

    test('should show error for password mismatch', async ({ page }) => {
      await page.goto('/register');
      await waitForPageLoad(page);

      await page.fill('input[type="email"]', 'test@example.com');
      await page.fill('input#password', 'Password123!');
      await page.fill('input#confirmPassword', 'DifferentPassword!');

      await page.click('button[type="submit"]');

      await expect(page.locator('text=Passwords do not match')).toBeVisible();
    });

    test('should show error for short password', async ({ page }) => {
      await page.goto('/register');
      await waitForPageLoad(page);

      await page.fill('input[type="email"]', 'test@example.com');
      await page.fill('input#password', 'short');
      await page.fill('input#confirmPassword', 'short');

      await page.click('button[type="submit"]');

      await expect(page.locator('text=Password must be at least 8 characters')).toBeVisible();
    });

    test('should navigate to login page', async ({ page }) => {
      await page.goto('/register');
      await waitForPageLoad(page);

      await page.click('text=Sign in');

      await expect(page).toHaveURL('/login');
    });
  });

  test.describe('Logout', () => {
    test('should logout and redirect to login', async ({ page }) => {
      // First, login
      await page.fill('input[type="email"]', 'admin@abvtrends.com');
      await page.fill('input[type="password"]', 'ABVTrendsAdmin2024!');
      await page.click('button[type="submit"]');

      // Wait for dashboard
      await expect(page).toHaveURL('/', { timeout: 10000 });
      await waitForPageLoad(page);

      // Wait for sidebar to show Sign Out button (indicating auth state loaded)
      const signOutButton = page.locator('text=Sign Out');
      await expect(signOutButton).toBeVisible({ timeout: 10000 });

      // Find and click logout button in sidebar
      await signOutButton.click();

      // Should redirect to login
      await expect(page).toHaveURL('/login', { timeout: 10000 });

      // Token should be cleared
      const token = await page.evaluate(() => localStorage.getItem('abvtrends_token'));
      expect(token).toBeNull();
    });
  });

  test.describe('Protected Routes', () => {
    test('should redirect unauthenticated users to login', async ({ page }) => {
      // Clear any existing auth
      await page.evaluate(() => localStorage.clear());

      // Try to access scraper page (admin only)
      await page.goto('/scraper');

      // Should redirect to login
      await expect(page).toHaveURL(/\/login/);
    });

    test('should allow authenticated admin to access scraper', async ({ page }) => {
      // Login as admin
      await page.fill('input[type="email"]', 'admin@abvtrends.com');
      await page.fill('input[type="password"]', 'ABVTrendsAdmin2024!');
      await page.click('button[type="submit"]');

      // Wait for dashboard
      await expect(page).toHaveURL('/', { timeout: 10000 });

      // Navigate to scraper
      await page.goto('/scraper');

      // Should stay on scraper page (not redirect to login)
      await expect(page).toHaveURL('/scraper', { timeout: 10000 });
      await expect(page.getByText('AI Scraper Monitor')).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Sidebar Authentication State', () => {
    test('should show sign in link when not authenticated', async ({ page }) => {
      await page.goto('/');
      await waitForPageLoad(page);

      // Look for sign in link in sidebar
      const sidebarUser = page.locator('[data-testid="sidebar-user"]');
      await expect(sidebarUser.locator('text=Sign In')).toBeVisible();
    });

    test('should show user email when authenticated', async ({ page }) => {
      // Login
      await page.fill('input[type="email"]', 'admin@abvtrends.com');
      await page.fill('input[type="password"]', 'ABVTrendsAdmin2024!');
      await page.click('button[type="submit"]');

      // Wait for dashboard
      await expect(page).toHaveURL('/', { timeout: 10000 });
      await waitForPageLoad(page);

      // Check sidebar shows user email
      const sidebarUser = page.locator('[data-testid="sidebar-user"]');
      await expect(sidebarUser.locator('text=admin@abvtrends.com')).toBeVisible({ timeout: 10000 });
    });

    test('should show admin badge for admin users', async ({ page }) => {
      // Login as admin
      await page.fill('input[type="email"]', 'admin@abvtrends.com');
      await page.fill('input[type="password"]', 'ABVTrendsAdmin2024!');
      await page.click('button[type="submit"]');

      // Wait for dashboard
      await expect(page).toHaveURL('/', { timeout: 10000 });
      await waitForPageLoad(page);

      // Check for admin badge (use exact match to avoid matching email)
      const sidebarUser = page.locator('[data-testid="sidebar-user"]');
      await expect(sidebarUser.getByText('Admin', { exact: true })).toBeVisible({ timeout: 10000 });
    });

    test('should show scraper nav item for admin users', async ({ page }) => {
      // Login as admin
      await page.fill('input[type="email"]', 'admin@abvtrends.com');
      await page.fill('input[type="password"]', 'ABVTrendsAdmin2024!');
      await page.click('button[type="submit"]');

      // Wait for dashboard
      await expect(page).toHaveURL('/', { timeout: 10000 });
      await waitForPageLoad(page);

      // Check for scraper nav item
      await expect(page.locator('[data-testid="nav-scraper"]')).toBeVisible({ timeout: 10000 });
    });
  });
});
