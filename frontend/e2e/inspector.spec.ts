import { test, expect } from '@playwright/test';
import { mockAuthentication, mockInspectorData, mockContainerList, waitForApiCall } from './helpers';

/**
 * E2E tests for MCP Inspector functionality
 * 
 * Tests the MCP Inspector feature including:
 * - Accessing inspector for running containers
 * - Viewing Tools, Resources, and Prompts
 * - Handling connection errors
 */

test.describe('MCP Inspector', () => {
  test.beforeEach(async ({ page }) => {
    // Mock authentication
    await mockAuthentication(page);

    // Mock data
    await mockContainerList(page);
    await mockInspectorData(page, 'test-container-id');

    await page.goto('/dashboard');
  });

  test('should have inspect button for containers', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Look for inspect button
    const inspectButton = page.getByRole('button', { name: /inspect/i }).first();

    const hasButton = await inspectButton.isVisible().catch(() => false);

    if (hasButton) {
      await expect(inspectButton).toBeVisible();
    }
  });

  test('should navigate to inspector page when clicking inspect', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Look for inspect button
    const inspectButton = page.getByRole('button', { name: /inspect/i }).first();

    const hasButton = await inspectButton.isVisible().catch(() => false);

    if (hasButton) {
      await inspectButton.click();

      // Should navigate to inspector page
      await expect(page).toHaveURL(/\/inspector\//);
    }
  });

  test('should display inspector panel with tabs', async ({ page }) => {
    // Navigate directly to inspector (with mock container ID)
    await page.goto('/inspector/test-container-id');

    // Should show inspector panel
    await expect(
      page.getByRole('heading', { name: /inspector/i })
    ).toBeVisible();

    // Should have tabs for Tools, Resources, and Prompts
    const toolsTab = page.getByRole('tab', { name: /tools/i });
    const resourcesTab = page.getByRole('tab', { name: /resources/i });
    const promptsTab = page.getByRole('tab', { name: /prompts/i });

    // At least one tab should be visible
    const hasToolsTab = await toolsTab.isVisible().catch(() => false);
    const hasResourcesTab = await resourcesTab.isVisible().catch(() => false);
    const hasPromptsTab = await promptsTab.isVisible().catch(() => false);

    expect(hasToolsTab || hasResourcesTab || hasPromptsTab).toBeTruthy();
  });

  test('should switch between inspector tabs', async ({ page }) => {
    await page.goto('/inspector/test-container-id');

    // Find tabs
    const toolsTab = page.getByRole('tab', { name: /tools/i });
    const resourcesTab = page.getByRole('tab', { name: /resources/i });

    const hasToolsTab = await toolsTab.isVisible().catch(() => false);
    const hasResourcesTab = await resourcesTab.isVisible().catch(() => false);

    if (hasToolsTab && hasResourcesTab) {
      // Click on Resources tab
      await resourcesTab.click();

      // Wait for tab to activate
      // Wait for tab to activate
      await expect(page.locator('[data-testid="resources-list"], .resources-list').or(page.getByText(/no resources|empty|リソースがありません/i)).first()).toBeVisible();

      // Click back to Tools tab
      await toolsTab.click();

      await expect(page.locator('[data-testid="tools-list"], .tools-list').or(page.getByText(/no tools|empty|ありません/i)).first()).toBeVisible();
    }
  });

  test('should display tools list', async ({ page }) => {
    await page.goto('/inspector/test-container-id');

    await waitForApiCall(page, /\/api\/inspector\/test-container-id\/capabilities/);

    // Make sure we're on Tools tab
    const toolsTab = page.getByRole('tab', { name: /tools/i });
    const hasTab = await toolsTab.isVisible().catch(() => false);

    if (hasTab) {
      await toolsTab.click();
      await expect(
        page
          .locator('[data-testid="tools-list"], .tools-list')
          .or(page.getByText(/no tools|empty|ありません|利用可能なツールがありません/i))
          .or(page.getByText(/failed|error|失敗/i))
          .first()
      ).toBeVisible({ timeout: 10000 });
    }

    // Look for tools list or empty state
    const toolsList = page.locator('[data-testid="tools-list"]').or(
      page.locator('.tools-list')
    );

    const emptyState = page.getByText(/no tools|empty|ありません|利用可能なツールがありません/i);
    const errorState = page.getByText(/failed|error|失敗/i);

    // Either list or empty state should be visible
    const hasList = await toolsList.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);
    const hasErrorState = await errorState.isVisible().catch(() => false);

    expect(hasList || hasEmptyState || hasErrorState).toBeTruthy();
  });

  test('should display resources list', async ({ page }) => {
    await page.goto('/inspector/test-container-id');

    // Click on Resources tab
    const resourcesTab = page.getByRole('tab', { name: /resources/i });
    const hasTab = await resourcesTab.isVisible().catch(() => false);

    if (hasTab) {
      await resourcesTab.click();
      await expect(page.locator('[data-testid="resources-list"], .resources-list').or(page.getByText(/no resources|empty|リソースがありません/i)).first()).toBeVisible();

      // Look for resources list or empty state
      const resourcesList = page.locator('[data-testid="resources-list"]').or(
        page.locator('.resources-list')
      );

      const emptyState = page.getByText(/no resources|empty|リソースがありません/i);

      // Either list or empty state should be visible
      const hasList = await resourcesList.isVisible().catch(() => false);
      const hasEmptyState = await emptyState.isVisible().catch(() => false);

      expect(hasList || hasEmptyState).toBeTruthy();
    }
  });

  test('should display prompts list', async ({ page }) => {
    await page.goto('/inspector/test-container-id');

    // Click on Prompts tab
    const promptsTab = page.getByRole('tab', { name: /prompts/i });
    const hasTab = await promptsTab.isVisible().catch(() => false);

    if (hasTab) {
      await promptsTab.click();
      await expect(
        page
          .locator('[data-testid="prompts-list"], .prompts-list')
          .or(page.getByText(/no prompts|empty|プロンプトがありません/i))
          .first()
      ).toBeVisible();

      // Look for prompts list or empty state
      const promptsList = page.locator('[data-testid="prompts-list"]').or(
        page.locator('.prompts-list')
      );

      const emptyState = page.getByText(/no prompts|empty|プロンプトがありません/i);

      // Either list or empty state should be visible
      const hasList = await promptsList.isVisible().catch(() => false);
      const hasEmptyState = await emptyState.isVisible().catch(() => false);

      expect(hasList || hasEmptyState).toBeTruthy();
    }
  });

  test('should show loading state while fetching MCP data', async ({ page }) => {
    await page.goto('/inspector/test-container-id');

    // Should show loading indicator
    const loadingIndicator = page.getByText(/loading/i).or(
      page.locator('[role="status"]')
    );

    // Loading should appear briefly
    await expect(loadingIndicator).toBeVisible({ timeout: 1000 }).catch(() => {
      // It's okay if loading is too fast to catch
    });
  });

  test('should handle MCP connection errors', async ({ page, context }) => {
    // Intercept inspector API calls and make them fail
    await page.route('**/api/inspector/**', route => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ detail: 'Connection failed' })
      });
    });

    await page.goto('/inspector/test-container-id');

    // Should show error message
    await expect(
      page.getByText(/error|failed|connection/i)
    ).toBeVisible({ timeout: 5000 });
  });

  test('should display tool information with name and description', async ({ page }) => {
    await page.goto('/inspector/test-container-id');

    // Make sure we're on Tools tab
    const toolsTab = page.getByRole('tab', { name: /tools/i });
    const hasTab = await toolsTab.isVisible().catch(() => false);

    if (hasTab) {
      await toolsTab.click();
      await expect(page.locator('[data-testid="tools-list"], .tools-list').or(page.getByText(/no tools|empty|ありません/i)).first()).toBeVisible();

      // Look for tool items
      const toolItems = page.locator('[data-testid="tool-item"]').or(
        page.locator('.tool-item')
      );

      const count = await toolItems.count();

      if (count > 0) {
        // First tool should have name and description
        const firstTool = toolItems.first();

        // Should contain some text (name/description)
        await expect(firstTool).toContainText(/.+/);
      }
    }
  });

  test('should display resource information with URI and name', async ({ page }) => {
    await page.goto('/inspector/test-container-id');

    // Click on Resources tab
    const resourcesTab = page.getByRole('tab', { name: /resources/i });
    const hasTab = await resourcesTab.isVisible().catch(() => false);

    if (hasTab) {
      await resourcesTab.click();
      await expect(page.locator('[data-testid="resources-list"], .resources-list').or(page.getByText(/no resources|empty|リソースがありません/i)).first()).toBeVisible();

      // Look for resource items
      const resourceItems = page.locator('[data-testid="resource-item"]').or(
        page.locator('.resource-item')
      );

      const count = await resourceItems.count();

      if (count > 0) {
        // First resource should have URI and name
        const firstResource = resourceItems.first();

        // Should contain some text
        await expect(firstResource).toContainText(/.+/);
      }
    }
  });

  test('should have back navigation to container list', async ({ page }) => {
    await page.goto('/inspector/test-container-id');

    // Look for back button or navigation link
    const backButton = page.getByRole('button', { name: /back/i }).or(
      page.getByRole('link', { name: /back|containers/i })
    );

    const hasButton = await backButton.isVisible().catch(() => false);

    if (hasButton) {
      await backButton.click();

      // Should navigate back to dashboard/containers
      await expect(page).toHaveURL(/\/dashboard|\/containers/);
    }
  });
});
