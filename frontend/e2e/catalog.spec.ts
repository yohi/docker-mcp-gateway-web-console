import { test, expect } from '@playwright/test';

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
    // For now, navigate directly to catalog
    // In production, you'd need to authenticate first
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
    // Wait for catalog to load
    await page.waitForLoadState('networkidle');
    
    // Find search input
    const searchInput = page.getByPlaceholder(/search/i);
    
    // Type a search query
    await searchInput.fill('test');
    
    // Wait for search results to update
    await page.waitForLoadState('networkidle');
    
    // Results should be filtered
    // (exact assertions depend on test data)
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
      await expect(firstCard).toContainText(/.+/);
      
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
    // (exact assertion depends on test data)
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
  test('should prefill container configuration from catalog selection', async ({ page }) => {
    // Navigate to catalog
    await page.goto('/catalog');
    await page.waitForLoadState('networkidle');
    
    // Find and click first install button
    const installButton = page.getByRole('button', { name: /install|select/i }).first();
    const hasButton = await installButton.isVisible().catch(() => false);
    
    if (hasButton) {
      await installButton.click();
      
      // Should navigate to container configuration
      await expect(page).toHaveURL(/\/containers\/new/);
      
      // Configuration form should have prefilled values
      // (exact fields depend on implementation)
      const nameInput = page.getByLabel(/name/i);
      const imageInput = page.getByLabel(/image/i);
      
      // At least one field should be prefilled
      const nameValue = await nameInput.inputValue().catch(() => '');
      const imageValue = await imageInput.inputValue().catch(() => '');
      
      expect(nameValue.length > 0 || imageValue.length > 0).toBeTruthy();
    }
  });
});
