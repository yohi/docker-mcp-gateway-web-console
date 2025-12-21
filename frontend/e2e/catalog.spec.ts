import { test, expect, Page } from '@playwright/test';
import { mockAuthentication, mockCatalogData, mockContainerList, waitForToast, mockRemoteServers } from './helpers';

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
    page.on('console', msg => console.log(`BROWSER LOG: ${msg.text()}`));
    page.on('request', req => {
      if (req.url().includes('api')) {
        console.log(`REQUEST: ${req.method()} ${req.url()}`);
      }
    });
    // Set up authentication and catalog data mocks
    await mockAuthentication(page);
    await mockCatalogData(page);
    await mockContainerList(page);
    await mockRemoteServers(page, []);

    // Navigate to catalog
    await page.goto('/catalog');
  });

  test('should display catalog page with search functionality', async ({ page }) => {
    // Check for main heading
    await expect(
      page.getByRole('heading', { name: /catalog|mcp.*server/i })
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
    await searchInput.fill('fetch');
    // Trigger search logic (debounced or immediate)
    await page.waitForTimeout(500);

    // Verify filtered results
    const serverNames = page.getByTestId('server-name');
    await expect(serverNames.filter({ hasText: /^fetch$/i })).toHaveCount(1);
    await expect(serverNames.filter({ hasText: /^filesystem$/i })).toHaveCount(0);
  });

  test('should display server cards with required information', async ({ page }) => {
    await page.waitForLoadState('networkidle');

    // Look for server cards - using data-testid from implementation
    const serverCards = page.locator('[data-testid="catalog-card"]');

    await expect(serverCards.first()).toBeVisible({ timeout: 10000 });

    // Should have cards
    const cardCount = await serverCards.count();
    expect(cardCount).toBeGreaterThan(0);

    const fetchCard = serverCards.filter({
      has: page.getByTestId('server-name').filter({ hasText: /^fetch$/i }),
    }).first();
    await expect(fetchCard.getByTestId('server-name')).toContainText('fetch');
    await expect(fetchCard.getByTestId('server-description')).toBeVisible();
    await expect(fetchCard.getByTestId('server-vendor')).toContainText('Docker');

    // Check for Install button
    const installButton = fetchCard.getByRole('button', { name: 'インストール' });
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
      page.getByRole('heading', { name: /No servers found|見つかりませんでした/i })
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
        name: 'fetch',
        image: 'docker/mcp-fetch:latest',
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
    const fetchCard = serverCards.filter({
      has: page.getByTestId('server-name').filter({ hasText: /^fetch$/i }),
    }).first();
    await expect(fetchCard).toBeVisible();
    await expect(
      fetchCard.getByText(/実行中|インストール済み/i)
    ).toBeVisible({ timeout: 10000 });
    await expect(fetchCard.getByRole('button', { name: /^インストール$/ })).toHaveCount(0);
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
    const fetchCard = page.locator('[data-testid="catalog-card"]').filter({
      has: page.getByTestId('server-name').filter({ hasText: /^fetch$/i }),
    }).first();
    await fetchCard.getByRole('button', { name: 'インストール' }).click();

    // 2. Verify Modal Opens
    const modal = page.locator('text=fetchをインストール'); // Or stricter selector
    await expect(modal).toBeVisible();

    // 3. Verify inputs
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
        if (postData.image === 'docker/mcp-fetch:latest' && postData.env.API_KEY === 'my-secret-key') {
          await route.fulfill({
            status: 201,
            contentType: 'application/json',
            body: JSON.stringify({
              container_id: 'new-container-id',
              name: 'fetch',
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

    const fetchCard = page.locator('[data-testid="catalog-card"]').filter({
      has: page.getByTestId('server-name').filter({ hasText: /^fetch$/i }),
    }).first();
    await fetchCard.getByRole('button', { name: 'インストール' }).click();

    const modal = page.locator('text=fetchをインストール');
    await expect(modal).toBeVisible();

    const keyInput = page.getByLabel('API_KEY');
    await keyInput.fill(''); // clear required secret

    const installButton = page.getByRole('button', { name: 'インストール' }).last();
    await installButton.click();

    await waitForToast(page, /必須項目が未入力です/i, 5000);
  });
});
