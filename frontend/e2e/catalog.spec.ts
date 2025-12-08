import { test, expect, Page } from '@playwright/test';
import { mockAuthentication, mockCatalogData, mockContainerList, waitForToast } from './helpers';

/**
 * E2E tests for Catalog browsing and installation flow
 * 
 * Tests the complete catalog workflow including:
 * - Browsing available MCP servers
 * - Searching and filtering
 * - Selecting a server for installation
 * - Installing via Modal
 */

test.describe('Catalog Browser', () => {
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

  test('should allow searching catalog items', async ({ page }) => {
    // Wait for initial load
    await page.waitForLoadState('networkidle');

    // Type a search query
    const searchInput = page.getByPlaceholder(/search/i);
    await searchInput.fill('Test MCP Server');
    // Trigger search logic (debounced or immediate)
    await page.waitForTimeout(500);

    // Verify filtered results
    const serverNames = page.getByTestId('server-name');
    await expect(serverNames.filter({ hasText: 'Test MCP Server' })).toHaveCount(1);
    await expect(serverNames.filter({ hasText: 'Another Test Server' })).toHaveCount(0);
  });

  test('should display server cards with required information', async ({ page }) => {
    await page.waitForLoadState('networkidle');

    // Look for server cards - using data-testid from implementation
    const serverCards = page.locator('[data-testid="catalog-card"]');

    // Should have cards
    await expect(serverCards).toHaveCount(2); // Based on mockCatalogData default

    const firstCard = serverCards.first();
    await expect(firstCard.getByTestId('server-name')).toContainText('Test MCP Server');
    await expect(firstCard.getByTestId('server-description')).toBeVisible();
    await expect(firstCard.getByTestId('server-vendor')).toContainText('Test Vendor');

    // Check for Install button
    const installButton = firstCard.getByRole('button', { name: 'インストール' });
    await expect(installButton).toBeVisible();
  });

  test('should show empty state when no results found', async ({ page }) => {
    await page.waitForLoadState('networkidle');

    // Search for something that won't match
    const searchInput = page.getByPlaceholder(/search/i);
    await searchInput.fill('xyznonexistentserver123');
    // Wait for SWR refetch debounce
    await page.waitForTimeout(800);

    // Should show empty state message
    await expect(
      page.getByRole('heading', { name: 'No servers found' })
    ).toBeVisible();
  });
});

test.describe('Catalog Installed State', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthentication(page);
    await mockCatalogData(page);
    await mockContainerList(page, [
      {
        id: 'existing-container',
        name: 'test-mcp-server',
        image: 'test/mcp-server:latest',
        status: 'running',
        created_at: new Date().toISOString(),
        ports: { '8080': 8080 },
      },
    ]);
    await page.goto('/catalog');
  });

  test('should show installed status and disable install', async ({ page }) => {
    await page.waitForLoadState('networkidle');

    const serverCards = page.locator('[data-testid="catalog-card"]');
    await expect(serverCards).toHaveCount(2);

    const firstCard = serverCards.first();
    await expect(
      firstCard.getByText(/実行中|インストール済み/)
    ).toBeVisible({ timeout: 10000 });
    await expect(firstCard.getByRole('button', { name: 'インストール' })).toHaveCount(0);
  });
});

test.describe('Catalog Installation Flow', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthentication(page);
    await mockCatalogData(page);
    await page.goto('/catalog');
  });

  test('should open install modal and submit installation', async ({ page }) => {
    await page.waitForLoadState('networkidle');

    // 1. Click Install on the first card
    const firstCard = page.locator('[data-testid="catalog-card"]').first();
    await firstCard.getByRole('button', { name: 'インストール' }).click();

    // 2. Verify Modal Opens
    const modal = page.locator('text=Test MCP Serverをインストール'); // Or stricter selector
    await expect(modal).toBeVisible();

    // 3. Verify inputs
    // Test MCP Server has PORT and API_KEY in mockCatalogData
    // PORT is a normal env, API_KEY is a secret
    const portInput = page.getByLabel('PORT');
    await expect(portInput).toBeVisible();
    await expect(portInput).toHaveValue('8080'); // Default value

    const keyInput = page.getByLabel('API_KEY'); // Should be found by label
    await expect(keyInput).toBeVisible();

    // 4. Fill required secret
    await keyInput.fill('my-secret-key');

    // 5. Mock Install API (includes query strings)
    await page.route('**/api/containers**', async (route) => {
      if (route.request().method() === 'POST') {
        const postData = route.request().postDataJSON();
        // Verify payload
        if (postData.image === 'test/mcp-server:latest' && postData.env.API_KEY === 'my-secret-key') {
          await route.fulfill({
            status: 201,
            contentType: 'application/json',
            body: JSON.stringify({
              container_id: 'new-container-id',
              name: 'Test MCP Server',
              status: 'running'
            })
          });
        } else {
          await route.abort('failed');
        }
      } else {
        await route.continue();
      }
    });

    // 6. Click Install in Modal
    // Note: Use a more specific selector if multiple 'インストール' buttons exist.
    // The one in the modal is usually the last one or inside the modal container.
    // But since the modal covers the background, usually only the modal button is actionable/visible to user flow?
    // Let's rely on text or specificity.
    // In our implementation, modal has buttons "キャンセル" and "インストール".
    const installButton = page.getByRole('button', { name: 'インストール' }).last();
    await installButton.click();

    // 7. Verify Success Toast
    await waitForToast(page, /installed successfully|インストールされました|インストールしました/i, 8000);

    // 8. Verify Modal Closes
    await expect(modal).not.toBeVisible({ timeout: 5000 });
  });

  test('should block installation when required envs are missing', async ({ page }) => {
    await page.waitForLoadState('networkidle');

    const firstCard = page.locator('[data-testid="catalog-card"]').first();
    await firstCard.getByRole('button', { name: 'インストール' }).click();

    const modal = page.locator('text=Test MCP Serverをインストール');
    await expect(modal).toBeVisible();

    const keyInput = page.getByLabel('API_KEY');
    await keyInput.fill(''); // clear required secret

    const installButton = page.getByRole('button', { name: 'インストール' }).last();
    await installButton.click();

    await waitForToast(page, /必須項目が未入力です/i, 5000);
  });
});
