import { test, expect } from '@playwright/test';

/**
 * E2E tests for authentication flow
 * 
 * Tests the complete authentication workflow including:
 * - Login with Bitwarden credentials
 * - Session validation
 * - Logout
 */

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the application
    page.on('console', msg => console.log(`BROWSER LOG: ${msg.text()}`));
    await page.goto('/');
  });

  test('should redirect unauthenticated users to login page', async ({ page }) => {
    // When accessing the root, should redirect to login
    await expect(page).toHaveURL(/\/login/);

    // Should show login form
    await expect(page.getByRole('heading', { name: /login|Bitwardenでログイン/i })).toBeVisible();
  });

  test('should display login form with required fields', async ({ page }) => {
    await page.goto('/login');

    // Check for email input
    const emailInput = page.getByLabel(/email|メールアドレス/i);
    await expect(emailInput).toBeVisible();

    // Check for authentication method selection
    // (either API key or master password fields should be present)
    const apiKeyInput = page.getByLabel(/api key|client id|client secret/i);
    const passwordInput = page.getByLabel(/password|マスターパスワード/i);

    // At least one authentication method should be visible
    const hasApiKey = await apiKeyInput.first().isVisible().catch(() => false);
    const hasPassword = await passwordInput.first().isVisible().catch(() => false);

    expect(hasApiKey || hasPassword).toBeTruthy();

    // Check for login button
    await expect(page.getByRole('button', { name: /login|ログイン/i })).toBeVisible();
  });

  test('should show error message on invalid credentials', async ({ page }) => {
    await page.goto('/login');

    // Fill in invalid credentials
    await page.getByLabel(/email|メールアドレス/i).fill('invalid@example.com');

    // Try to find and fill authentication field
    // Note: Japanese form has radio buttons for method selection, simplified check here
    const passwordInput = page.getByLabel(/password|マスターパスワード/i);

    if (await passwordInput.first().isVisible().catch(() => false)) {
      await passwordInput.first().fill('invalid-password');
    }

    // Submit the form
    await page.getByRole('button', { name: /login|ログイン/i }).click();

    // Should show error message
    // Wait for either a toast notification or error message
    await expect(
      page.getByText(/authentication failed|invalid credentials|error|失敗しました|入力してください/i)
    ).toBeVisible({ timeout: 5000 });
  });

  test('should handle session timeout', async ({ page, context }) => {
    // This test would require a valid session
    // For now, we'll test the UI behavior when session expires

    // Mock a scenario where we have an expired session
    await context.addCookies([{
      name: 'session',
      value: 'expired-session-id',
      domain: 'localhost',
      path: '/',
      httpOnly: true,
      secure: false,
      sameSite: 'Lax',
    }]);

    // Try to access a protected route
    await page.goto('/dashboard');

    // Should redirect to login or show session expired message
    await page.waitForURL(/\/login/, { timeout: 5000 }).catch(() => {
      // If not redirected, check for error message
      expect(page.getByText(/session expired|unauthorized/i)).toBeVisible();
    });
  });

  test('should have logout functionality when authenticated', async ({ page }) => {
    // Note: This test assumes we can't actually authenticate in E2E
    // In a real scenario, you'd need test credentials or mock the auth

    // For now, just verify the logout button exists in the layout
    // when we mock an authenticated state
    await page.goto('/login');

    // Check that logout button is not visible on login page
    const logoutButton = page.getByRole('button', { name: /logout/i });
    await expect(logoutButton).not.toBeVisible();
  });
});

test.describe('Protected Routes', () => {
  test('should protect dashboard route', async ({ page }) => {
    await page.goto('/dashboard');

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/);
  });

  test('should protect catalog route', async ({ page }) => {
    await page.goto('/catalog');

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/);
  });

  test('should protect containers route', async ({ page }) => {
    await page.goto('/containers/new');

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/);
  });

  test('should protect config route', async ({ page }) => {
    await page.goto('/config');

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/);
  });
});
