/**
 * Helper functions for E2E tests
 */

import { Page } from '@playwright/test';

/**
 * Mock authentication by setting session cookie
 * 
 * Note: In a real scenario, you would either:
 * 1. Use test Bitwarden credentials
 * 2. Mock the authentication API
 * 3. Use a test authentication endpoint
 */
export async function mockAuthentication(page: Page) {
  // Set a mock session cookie
  await page.context().addCookies([{
    name: 'session',
    value: 'test-session-id',
    domain: 'localhost',
    path: '/',
    httpOnly: true,
    secure: false,
    sameSite: 'Lax',
  }]);
  
  // Mock the session validation API
  await page.route('**/api/auth/session', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        valid: true,
        expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
      }),
    });
  });
}

/**
 * Mock catalog data for testing
 */
export async function mockCatalogData(page: Page) {
  await page.route('**/api/catalog**', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        servers: [
          {
            id: 'test-server-1',
            name: 'Test MCP Server',
            description: 'A test MCP server for E2E testing',
            category: 'testing',
            docker_image: 'test/mcp-server:latest',
            default_env: {
              PORT: '8080',
              API_KEY: '{{ bw:test-id:api_key }}',
            },
            required_secrets: ['API_KEY'],
          },
          {
            id: 'test-server-2',
            name: 'Another Test Server',
            description: 'Another test server',
            category: 'utilities',
            docker_image: 'test/another-server:latest',
            default_env: {},
            required_secrets: [],
          },
        ],
        total: 2,
        cached: false,
      }),
    });
  });
}

/**
 * Mock container list data
 */
export async function mockContainerList(page: Page, containers: any[] = []) {
  await page.route('**/api/containers', route => {
    if (route.request().method() === 'GET') {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          containers: containers.length > 0 ? containers : [
            {
              id: 'test-container-1',
              name: 'test-mcp-server',
              image: 'test/mcp-server:latest',
              status: 'running',
              created_at: new Date().toISOString(),
              ports: { '8080': 8080 },
            },
          ],
        }),
      });
    } else {
      route.continue();
    }
  });
}

/**
 * Mock MCP inspector data
 */
export async function mockInspectorData(page: Page, containerId: string) {
  // Mock tools
  await page.route(`**/api/inspector/${containerId}/tools`, route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        tools: [
          {
            name: 'test_tool',
            description: 'A test tool',
            input_schema: {
              type: 'object',
              properties: {
                param1: { type: 'string' },
              },
            },
          },
        ],
      }),
    });
  });
  
  // Mock resources
  await page.route(`**/api/inspector/${containerId}/resources`, route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        resources: [
          {
            uri: 'test://resource',
            name: 'Test Resource',
            description: 'A test resource',
            mime_type: 'application/json',
          },
        ],
      }),
    });
  });
  
  // Mock prompts
  await page.route(`**/api/inspector/${containerId}/prompts`, route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        prompts: [
          {
            name: 'test_prompt',
            description: 'A test prompt',
            arguments: [],
          },
        ],
      }),
    });
  });
}

/**
 * Wait for API call to complete
 */
export async function waitForApiCall(page: Page, urlPattern: string | RegExp) {
  return page.waitForResponse(
    response => {
      const url = response.url();
      if (typeof urlPattern === 'string') {
        return url.includes(urlPattern);
      }
      return urlPattern.test(url);
    },
    { timeout: 5000 }
  );
}

/**
 * Fill form field by label
 */
export async function fillFormField(page: Page, label: string | RegExp, value: string) {
  const input = page.getByLabel(label);
  await input.fill(value);
}

/**
 * Click button by name
 */
export async function clickButton(page: Page, name: string | RegExp) {
  const button = page.getByRole('button', { name });
  await button.click();
}

/**
 * Wait for toast notification
 */
export async function waitForToast(page: Page, message?: string | RegExp) {
  const toast = message 
    ? page.getByText(message)
    : page.locator('[role="alert"]').or(page.locator('.toast'));
  
  await toast.waitFor({ state: 'visible', timeout: 5000 });
  return toast;
}
