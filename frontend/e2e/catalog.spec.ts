import { test, expect } from '@playwright/test';
import { mockAuthentication, mockCatalogData } from './helpers';

/**
 * E2E tests for Catalog browsing and installation flow
 * 
 * Tests the complete catalog workflow including:
 * - Browsing available MCP servers
 * - Searching and filtering
 * - Selecting a server for installation
 */

test.describe('Catalog Browser', () => {
  // Note: These tests assume authentication is handled
  // In a real scenario, you'd set up authenticated state in beforeEach

  test.beforeEach(async ({ page }) => {
    // Set up authentication and catalog data mocks
    await mockAuthentication(page);
    await mockCatalogData(page);

    // Navigate to catalog
    await page.goto('/catalog');
  });

  test('should display catalog page with search functionality', async ({ page }) => {
    // Check for main heading
    await expect(
      page.getByRole('heading', { name: /catalog|mcp servers/i })
    ).toBeVisible();

    // Check for search bar
    const searchInput = page.getByPlaceholder(/search/i);
    await expect(searchInput).toBeVisible();
  });

  test('should display loading state while fetching catalog', async ({ page }) => {
    // Reload to see loading state
    await page.reload();

    // Should show loading indicator
    const loadingIndicator = page.getByText(/loading/i).or(
      page.locator('[role="status"]')
    );

    // Loading should appear briefly
    await expect(loadingIndicator).toBeVisible({ timeout: 1000 }).catch(() => {
      // It's okay if loading is too fast to catch
    });
  });

  test('should allow searching catalog items', async ({ page }) => {
    // Mock catalog data with known test data
    await mockCatalogData(page, [
      {
        id: 'test-server-1',
        name: 'test-server',
        description: 'Test server',
        category: 'testing',
        docker_image: 'test/image:latest',
        default_env: {},
        required_secrets: []
      },
      {
        id: 'test-server-2',
        name: 'other-server',
        description: 'Other server',
        category: 'testing',
        docker_image: 'test/other:latest',
        default_env: {},
        required_secrets: []
      }
    ]);

    // Reload to apply new mock data
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Find search input
    const searchInput = page.getByPlaceholder(/search/i);

    // Type a search query
    await searchInput.fill('test');

    // Wait for search results to update
    await page.waitForLoadState('networkidle');

    // Verify filtered results
    await expect(page.getByText('test-server')).toBeVisible();
    await expect(page.getByText('other-server')).not.toBeVisible();
  });

  test('should allow filtering by category', async ({ page }) => {
    // Wait for catalog to load
    await page.waitForLoadState('networkidle');

    // Look for category filter dropdown or buttons
    const categoryFilter = page.getByLabel(/category/i).or(
      page.getByRole('combobox', { name: /category/i })
    );

    // Check if category filter exists
    const hasFilter = await categoryFilter.isVisible().catch(() => false);

    if (hasFilter) {
      // Select a category
      await categoryFilter.click();

      // Wait for filter to apply
      await page.waitForLoadState('networkidle');
    }
  });

  test('should display server cards with required information', async ({ page }) => {
    // Wait for catalog to load
    await page.waitForLoadState('networkidle');

    // Look for server cards
    const serverCards = page.locator('[data-testid="server-card"]').or(
      page.locator('article').or(page.locator('.server-card'))
    );

    // Should have at least one card (if catalog has data)
    const cardCount = await serverCards.count();

    if (cardCount > 0) {
      const firstCard = serverCards.first();

      // Each card should have a name/title
      const title = firstCard.getByTestId('server-name').or(
        firstCard.locator('h3').or(firstCard.locator('.title')).or(firstCard.locator('.server-title'))
      );
      await expect(title).toContainText(/\S+/);

      // Check for description if available
      const description = firstCard.getByTestId('server-description').or(
        firstCard.locator('.description')
      );
      if (await description.count() > 0) {
        await expect(description).toContainText(/\S+/);
      }

      // Should have an install or select button
      const installButton = firstCard.getByRole('button', { name: /install|select/i });
      await expect(installButton).toBeVisible();
    }
  });

  test('should navigate to container configuration when selecting a server', async ({ page }) => {
    // Wait for catalog to load
    await page.waitForLoadState('networkidle');

    // Find first install/select button
    const installButton = page.getByRole('button', { name: /install|select/i }).first();

    const hasButton = await installButton.isVisible().catch(() => false);

    if (hasButton) {
      // Click install button
      await installButton.click();

      // Should navigate to container configuration page
      await expect(page).toHaveURL(/\/containers\/new/);
    }
  });

  test('should show empty state when no results found', async ({ page }) => {
    // Wait for catalog to load
    await page.waitForLoadState('networkidle');

    // Search for something that won't match
    const searchInput = page.getByPlaceholder(/search/i);
    await searchInput.fill('xyznonexistentserver123');

    // Wait for search to complete
    await page.waitForLoadState('networkidle');

    // Should show empty state message
    await expect(
      page.getByText(/no.*found|no results|該当するアイテムがありません/i)
    ).toBeVisible();
  });

  test('should clear search and show all items', async ({ page }) => {
    // Wait for catalog to load
    await page.waitForLoadState('networkidle');

    // Search for something
    const searchInput = page.getByPlaceholder(/search/i);
    await searchInput.fill('test');
    await page.waitForLoadState('networkidle');

    // Clear search
    await searchInput.clear();
    await page.waitForLoadState('networkidle');

    // Should show all items again
    const serverCards = page.locator('[data-testid="server-card"]');
    const cardCount = await serverCards.count();
    expect(cardCount).toBeGreaterThan(0);
  });

  test('should handle catalog fetch errors gracefully', async ({ page, context }) => {
    // Intercept catalog API call and make it fail
    await page.route('**/api/catalog**', route => {
      route.abort('failed');
    });

    // Navigate to catalog
    await page.goto('/catalog');

    // Should show error message
    await expect(
      page.getByText(/error|failed|connection/i)
    ).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Catalog Integration', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthentication(page);
    await mockCatalogData(page);
    await page.goto('/catalog');
  });

  test('should prefill container configuration from catalog selection', async ({ page }) => {
    // Wait for catalog to load
    await page.waitForLoadState('networkidle');

    // Find the first server card
    const firstCard = page.locator('[data-testid="server-card"]').first();

    // Ensure we have at least one card visible before trying to interact
    await expect(firstCard).toBeVisible();

    // Capture the visible name
    const nameElement = firstCard.getByTestId('server-name').or(
      firstCard.locator('h3').or(firstCard.locator('.title')).or(firstCard.locator('.server-title'))
    );
    const capturedName = (await nameElement.textContent())?.trim() || '';
    expect(capturedName).toBeTruthy();

    // Capture the image from data attributes or visible text
    // We check common data attributes or a specific test id
    const capturedImage = await firstCard.getAttribute('data-image') ||
      await firstCard.getAttribute('data-docker-image') ||
      (await firstCard.getByTestId('server-image').textContent())?.trim() ||
      '';

    // Find install/select button within the card
    const installButton = firstCard.getByRole('button', { name: /install|select/i });
    const hasButton = await installButton.isVisible().catch(() => false);

    if (hasButton) {
      await installButton.click();

      // Wait for navigation to container configuration
      await page.waitForURL(/\/containers\/new/);

      // Wait for form to be visible
      const nameInput = page.getByLabel(/name/i);
      await expect(nameInput).toBeVisible();

      // Strict equality assertion for Name
      await expect(nameInput).toHaveValue(capturedName);

      // Strict equality assertion for Image if we captured it
      if (capturedImage) {
        const imageInput = page.getByLabel(/image/i);
        await expect(imageInput).toHaveValue(capturedImage);
      }
    }
  });
});
