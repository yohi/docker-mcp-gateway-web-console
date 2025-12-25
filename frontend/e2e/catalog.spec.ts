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

/**
 * Catalog Source Selector Tests
 *
 * Task 14.1: Dockerソース選択時のカタログ表示をテストする
 * Requirements: 1.1, 1.2, 1.4
 */
test.describe('Catalog Source Selection', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthentication(page);
    await mockContainerList(page);
    await mockRemoteServers(page, []);
  });

  test('@docker-source should display catalog when Docker source is selected', async ({ page }) => {
    // Mock Docker catalog response
    await mockCatalogData(page);

    // Navigate to catalog page
    await page.goto('/catalog');
    await page.waitForLoadState('networkidle');

    // Verify catalog source selector is visible
    const sourceSelector = page.getByTestId('catalog-source-selector');
    await expect(sourceSelector).toBeVisible();

    // Verify Docker is the default selected source
    const selectElement = page.locator('#catalog-source-select');
    await expect(selectElement).toHaveValue('docker');

    // Verify catalog list displays
    const serverCards = page.locator('[data-testid="catalog-card"]');
    await expect(serverCards.first()).toBeVisible({ timeout: 10000 });

    // Verify at least one server is shown
    const cardCount = await serverCards.count();
    expect(cardCount).toBeGreaterThan(0);

    // Verify Docker source label is displayed
    await expect(selectElement.locator('option[value="docker"]')).toHaveText('Docker MCP Catalog');
  });

  test('@docker-source should show loading state while fetching catalog', async ({ page }) => {
    // Mock delayed catalog response to observe loading state
    let resolveRoute: (value: unknown) => void;
    const routePromise = new Promise((resolve) => {
      resolveRoute = resolve;
    });

    await page.route('**/api/catalog**', async (route) => {
      console.log(`MOCK HIT (delayed catalog): ${route.request().url()}`);
      // Wait for manual resolution to simulate loading
      await routePromise;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          servers: [],
          total: 0,
          page: 1,
          page_size: 8,
          categories: [],
          cached: false,
        }),
      });
    });

    // Navigate to catalog page
    await page.goto('/catalog');

    // Verify loading state is displayed
    const loadingIndicator = page.getByText(/読み込み中|loading/i);
    await expect(loadingIndicator).toBeVisible({ timeout: 5000 });

    // Resolve the route to complete loading
    resolveRoute!(undefined);

    // Verify loading state disappears
    await expect(loadingIndicator).not.toBeVisible({ timeout: 5000 });
  });

  test('@official-source should display catalog when Official source is selected', async ({ page }) => {
    // Mock both Docker (initial) and Official catalog responses
    await mockCatalogData(page);

    // Navigate to catalog page
    await page.goto('/catalog');
    await page.waitForLoadState('networkidle');

    // Verify catalog source selector is visible
    const sourceSelector = page.getByTestId('catalog-source-selector');
    await expect(sourceSelector).toBeVisible();

    // Initially Docker is selected (default)
    const selectElement = page.locator('#catalog-source-select');
    await expect(selectElement).toHaveValue('docker');

    // Wait for initial catalog to load
    const serverCards = page.locator('[data-testid="catalog-card"]');
    await expect(serverCards.first()).toBeVisible({ timeout: 10000 });

    // Change to Official source
    await selectElement.selectOption('official');

    // Verify Official is now selected
    await expect(selectElement).toHaveValue('official');

    // Wait for the catalog to update (either from cache or new request)
    // We verify the cards are still visible after source change
    await expect(serverCards.first()).toBeVisible({ timeout: 10000 });

    // Verify at least one server is shown
    const cardCount = await serverCards.count();
    expect(cardCount).toBeGreaterThan(0);

    // Verify Official source label is displayed
    await expect(selectElement.locator('option[value="official"]')).toHaveText('Official MCP Registry');
  });

  test('@official-source should switch sources without page reload', async ({ page }) => {
    // Mock catalog data for both sources
    await mockCatalogData(page);

    // Navigate to catalog page
    await page.goto('/catalog');
    await page.waitForLoadState('networkidle');

    const selectElement = page.locator('#catalog-source-select');
    const serverCards = page.locator('[data-testid="catalog-card"]');

    // Initially on Docker source
    await expect(selectElement).toHaveValue('docker');
    await expect(serverCards.first()).toBeVisible({ timeout: 10000 });

    // Track page navigation (should NOT happen)
    let pageNavigated = false;
    page.on('framenavigated', () => {
      pageNavigated = true;
    });

    // Switch to Official source
    await selectElement.selectOption('official');

    // Verify no page reload occurred
    expect(pageNavigated).toBe(false);

    // Verify Official is now selected
    await expect(selectElement).toHaveValue('official');

    // Verify catalog list is still visible (content might be same in mock)
    await expect(serverCards.first()).toBeVisible({ timeout: 10000 });

    // Switch back to Docker
    await selectElement.selectOption('docker');

    // Verify still no page reload
    expect(pageNavigated).toBe(false);

    // Verify Docker is selected again
    await expect(selectElement).toHaveValue('docker');
    await expect(serverCards.first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthentication(page);
    await mockContainerList(page);
    await mockRemoteServers(page, []);
  });

  test('@rate-limit should display countdown and retry button when rate limited', async ({ page }) => {
    test.setTimeout(20000); // Extend timeout to 20 seconds for countdown test

    // Mock rate limit error from the start
    await page.route('**/api/catalog**', async (route) => {
      console.log(`MOCK HIT (rate limit error): ${route.request().url()}`);
      await route.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Rate limit exceeded. Please try again later.',
          error_code: 'rate_limited',
          retry_after_seconds: 3,
        }),
      });
    });

    // Navigate to catalog page
    await page.goto('/catalog');
    await page.waitForLoadState('networkidle');

    // Verify rate limit error message is displayed
    const errorHeading = page.getByRole('heading', { name: /レート制限に達しました/i });
    await expect(errorHeading).toBeVisible({ timeout: 10000 });

    // Verify countdown is displayed
    const countdownContainer = page.getByTestId('rate-limit-countdown');
    await expect(countdownContainer).toBeVisible();

    // Check initial countdown text (shows "3 秒")
    const countdownText = countdownContainer.locator('strong');
    await expect(countdownText).toHaveText('3');

    // Verify retry button is shown (but disabled initially)
    const retryButton = page.getByRole('button', { name: /再試行/i });
    await expect(retryButton).toBeVisible();
    await expect(retryButton).toBeDisabled();

    // Wait for countdown to decrease
    await page.waitForTimeout(1500);

    // Verify countdown has decreased (should show 1 or 2)
    await expect(countdownText).toHaveText(/[12]/);

    // Verify button is still disabled
    await expect(retryButton).toBeDisabled();
  });

  test('@upstream-failure should display retry button when upstream unavailable', async ({ page }) => {
    // Mock upstream unavailable error response (503)
    await page.route('**/api/catalog**', async (route) => {
      console.log(`MOCK HIT (upstream unavailable): ${route.request().url()}`);
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Upstream service is temporarily unavailable.',
          error_code: 'upstream_unavailable',
        }),
      });
    });

    // Navigate to catalog page
    await page.goto('/catalog');
    await page.waitForLoadState('networkidle');

    // Verify upstream unavailable error heading is displayed
    const errorHeading = page.getByRole('heading', { name: /上流サービスが利用できません/i });
    await expect(errorHeading).toBeVisible({ timeout: 10000 });

    // Verify retry button is displayed
    const retryButton = page.getByRole('button', { name: /再試行|retry/i });
    await expect(retryButton).toBeVisible({ timeout: 5000 });

    // Mock successful response for retry
    await page.unroute('**/api/catalog**');
    await mockCatalogData(page);

    // Click retry button
    await retryButton.click();

    // Verify catalog loads successfully after retry
    const serverCards = page.locator('[data-testid="catalog-card"]');
    await expect(serverCards.first()).toBeVisible({ timeout: 10000 });

    // Verify at least one server is shown
    const cardCount = await serverCards.count();
    expect(cardCount).toBeGreaterThan(0);
  });
});
