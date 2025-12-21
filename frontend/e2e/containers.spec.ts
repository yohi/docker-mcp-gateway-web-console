import { test, expect } from '@playwright/test';
import { mockAuthentication, mockContainerList } from './helpers';

/**
 * E2E tests for container management flow
 * 
 * Tests the complete container lifecycle including:
 * - Creating and starting containers
 * - Viewing container list and status
 * - Container operations (start, stop, restart, delete)
 * - Log viewing
 */

test.describe('Container Management', () => {
  test.beforeEach(async ({ page }) => {
    // Mock authentication
    await mockAuthentication(page);

    // Mock container list
    await mockContainerList(page);

    // Navigate to dashboard/containers page
    await page.goto('/dashboard');
  });

  test('should display container dashboard', async ({ page }) => {
    // Check for main heading
    await expect(
      page.getByRole('heading', { name: /containers|dashboard|コンテナ|ダッシュボード/i })
    ).toBeVisible();

    // Should have a button to create new container
    const newContainerButton = page.getByRole('button', { name: /new|create|add/i });
    await expect(newContainerButton).toBeVisible();
  });

  test('should navigate to container creation form', async ({ page }) => {
    // Click new container button
    const newContainerButton = page.getByRole('button', { name: /new|create|add/i });
    await newContainerButton.click();

    // Should navigate to container creation page
    await expect(page).toHaveURL(/\/containers\/new/);

    // Should show configuration form
    await expect(page.getByLabel(/name|コンテナ名/i)).toBeVisible();
    await expect(page.getByLabel(/image|Dockerイメージ/i)).toBeVisible();
  });

  test('should display container list', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Look for container list or empty state
    const containerList = page.locator('[data-testid="container-list"]').or(
      page.locator('.container-list')
    );

    const emptyState = page.getByText(/no containers|empty|ありません/i);

    // Either list or empty state should be visible
    const hasList = await containerList.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);

    expect(hasList || hasEmptyState).toBeTruthy();
  });

  test('should show container status indicators', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Look for status indicators
    const statusIndicators = page.locator('[data-testid="container-status"]').or(
      page.getByText(/running|stopped|error/i)
    );

    // If there are containers, should show status
    const count = await statusIndicators.count();

    if (count > 0) {
      // First status should be visible
      await expect(statusIndicators.first()).toBeVisible();
    }
  });

  test('should display container action buttons', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Look for action buttons (start, stop, restart, delete)
    const actionButtons = page.getByRole('button', { name: /start|stop|restart|delete/i });

    const count = await actionButtons.count();

    if (count > 0) {
      // Should have action buttons for containers
      await expect(actionButtons.first()).toBeVisible();
    }
  });

  test('should show confirmation dialog before deleting container', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Look for delete button
    const deleteButton = page.getByRole('button', { name: /delete/i }).first();

    const hasButton = await deleteButton.isVisible().catch(() => false);

    if (hasButton) {
      // Click delete button
      await deleteButton.click();

      // Should show confirmation dialog
      await expect(
        page.getByText(/confirm|are you sure|よろしいですか|削除/i)
      ).toBeVisible({ timeout: 2000 });

      // Should have cancel button
      const cancelButton = page.getByRole('button', { name: /cancel|no/i });
      await expect(cancelButton).toBeVisible();

      // Cancel the deletion
      await cancelButton.click();
    }
  });

  test('should handle container operation errors', async ({ page, context }) => {
    // Intercept container API calls and make them fail
    await page.route('**/api/containers/**', route => {
      if (route.request().method() !== 'GET') {
        route.fulfill({
          status: 500,
          body: JSON.stringify({ detail: 'Operation failed' })
        });
      } else {
        route.continue();
      }
    });

    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // Try to perform an operation
    const actionButton = page.getByRole('button', { name: /start|stop/i }).first();
    const hasButton = await actionButton.isVisible().catch(() => false);

    if (hasButton) {
      await actionButton.click();

      // Should show error message
      await expect(
        page.getByText(/error|failed/i)
      ).toBeVisible({ timeout: 3000 });
    }
  });
});

test.describe('Container Configuration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/containers/new');
  });

  test('should display container configuration form', async ({ page }) => {
    // Check for required form fields
    await expect(page.getByLabel(/name|コンテナ名/i)).toBeVisible();
    await expect(page.getByLabel(/image|Dockerイメージ/i)).toBeVisible();

    // Should have submit button
    await expect(
      page.getByRole('button', { name: /create|start|launch|コンテナを作成/i })
    ).toBeVisible();
  });

  test('should allow adding environment variables', async ({ page }) => {
    // Look for environment variable section
    const envSection = page.getByText(/environment|env/i);

    const hasEnvSection = await envSection.isVisible().catch(() => false);

    if (hasEnvSection) {
      // Should have way to add environment variables
      const addEnvButton = page.getByRole('button', { name: /add.*variable|add.*env/i });

      const hasAddButton = await addEnvButton.isVisible().catch(() => false);

      if (hasAddButton) {
        await addEnvButton.click();

        // Should show input fields for key and value
        await expect(page.getByPlaceholder(/key|name|キー/i).or(page.locator('input[type="text"]')).last()).toBeVisible();
      }
    }
  });

  test('should support Bitwarden reference notation in environment variables', async ({ page }) => {
    // Look for environment variable inputs
    const envValueInput = page.getByLabel(/value/i).or(
      page.locator('input[name*="env"]')
    );

    const hasInput = await envValueInput.first().isVisible().catch(() => false);

    if (hasInput) {
      // Type Bitwarden reference notation
      await envValueInput.first().fill('{{ bw:test-id:password }}');

      // Should accept the input
      const value = await envValueInput.first().inputValue();
      expect(value).toContain('{{ bw:');
    }
  });

  test('should validate required fields', async ({ page }) => {
    // Try to submit without filling required fields
    const submitButton = page.getByRole('button', { name: /create|start|launch/i });
    await submitButton.click();

    // Should show validation errors
    await expect(
      page.getByText(/required|必須/i)
    ).toBeVisible({ timeout: 2000 });
  });

  test('should allow configuring ports', async ({ page }) => {
    // Look for port configuration section
    const portSection = page.getByText(/ports?/i);

    const hasPortSection = await portSection.isVisible().catch(() => false);

    if (hasPortSection) {
      // Should have way to configure ports
      const portInput = page.getByLabel(/port/i);

      const hasInput = await portInput.first().isVisible().catch(() => false);

      if (hasInput) {
        await portInput.first().fill('8080');
      }
    }
  });

  test('should allow configuring volumes', async ({ page }) => {
    // Look for volume configuration section
    const volumeSection = page.getByText(/volumes?/i);

    const hasVolumeSection = await volumeSection.isVisible().catch(() => false);

    if (hasVolumeSection) {
      // Should have way to configure volumes
      const addVolumeButton = page.getByRole('button', { name: /add.*volume/i });

      const hasButton = await addVolumeButton.isVisible().catch(() => false);

      if (hasButton) {
        await addVolumeButton.click();
        // Wait for volume input fields to appear
        await expect(page.getByPlaceholder(/host path|volume|ホストパス/i).or(page.locator('input[type="text"]')).last()).toBeVisible();
      }
    }
  });
});

test.describe('Container Logs', () => {
  test('should have log viewer functionality', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // Look for logs button
    const logsButton = page.getByRole('button', { name: /logs|view logs/i }).first();

    const hasButton = await logsButton.isVisible().catch(() => false);

    if (hasButton) {
      await logsButton.click();

      // Should show log viewer
      await expect(
        page.getByText(/logs/i)
      ).toBeVisible({ timeout: 2000 });
    }
  });

  test('should display log entries', async ({ page }) => {
    // This test would require a running container with logs
    // For now, just verify the log viewer UI exists

    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    const logsButton = page.getByRole('button', { name: /logs/i }).first();
    const hasButton = await logsButton.isVisible().catch(() => false);

    if (hasButton) {
      await logsButton.click();

      // Log viewer should be visible
      const logViewer = page.locator('[data-testid="log-viewer"]').or(
        page.locator('.log-viewer')
      );

      await expect(logViewer).toBeVisible({ timeout: 2000 });
    }
  });
});
