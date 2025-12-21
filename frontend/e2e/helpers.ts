/**
 * Helper functions for E2E tests
 */

import { Page } from '@playwright/test';
import type { CatalogItem } from '@/lib/types/catalog';
import registryCatalog from './fixtures/mcp-registry.json';

export const TEST_SESSION_ID = 'test-session-id';
export const TEST_LOGIN_CREDENTIALS = {
  method: 'api_key' as const,
  email: 'test@example.com',
  clientId: 'test-client-id',
  clientSecret: 'test-client-secret',
  masterPassword: 'test-master-password',
};

type MockLoginCredentials = {
  method: 'api_key' | 'master_password';
  email: string;
  clientId?: string;
  clientSecret?: string;
  masterPassword: string;
  twoStepLoginMethod?: number;
  twoStepLoginCode?: string;
};

type MockLoginOptions = {
  credentials?: MockLoginCredentials;
  sessionId?: string;
  createdAt?: string;
  expiresAt?: string;
};

type CatalogMockServer =
  & Partial<Pick<CatalogItem, 'id' | 'name' | 'description' | 'vendor' | 'category'>>
  & Record<string, unknown>;
type CatalogFixturePayload = { servers?: CatalogMockServer[] } | CatalogMockServer[];

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
    value: TEST_SESSION_ID,
    domain: 'localhost',
    path: '/',
    httpOnly: true,
    secure: false,
    sameSite: 'Lax',
  }]);

  // Ensure session id is available for API headers used in hooks
  await page.addInitScript((args) => {
    try {
      const now = new Date().toISOString();
      const session = {
        session_id: args.sessionId,
        user_email: args.userEmail,
        created_at: now,
        expires_at: args.expiresAt,
      };
      window.localStorage.setItem('session', JSON.stringify(session));
      window.localStorage.setItem('session_id', args.sessionId);
    } catch (e) {
      // ignore storage errors in headless context
    }
  }, { sessionId: TEST_SESSION_ID, userEmail: TEST_LOGIN_CREDENTIALS.email, expiresAt: new Date(Date.now() + 30 * 60 * 1000).toISOString() });

  // Mock the session validation API
  console.log('Registering session mock...');
  await page.route(url => url.toString().includes('/api/auth/session'), route => {
    console.log(`MOCK HIT (session): ${route.request().url()}`);
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        valid: true,
        session_id: TEST_SESSION_ID,
        user_email: TEST_LOGIN_CREDENTIALS.email,
        created_at: new Date(Date.now() - 60 * 1000).toISOString(),
        expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
      }),
    });
  });
}

export async function mockLogin(page: Page, options: MockLoginOptions = {}) {
  const credentials: MockLoginCredentials = {
    ...TEST_LOGIN_CREDENTIALS,
    ...options.credentials,
  };
  const sessionId = options.sessionId ?? TEST_SESSION_ID;
  const now = Date.now();
  const createdAt = options.createdAt ?? new Date(now - 60 * 1000).toISOString();
  const expiresAt = options.expiresAt ?? new Date(now + 30 * 60 * 1000).toISOString();

  await page.route(url => url.toString().includes('/api/auth/login'), async route => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }

    let body: any = null;
    try {
      body = await route.request().postDataJSON();
    } catch {
      body = null;
    }

    const matchesMethod = body?.method === credentials.method;
    const matchesEmail = body?.email === credentials.email;
    const matchesMasterPassword = body?.master_password === credentials.masterPassword;
    const matchesTwoStepMethod =
      credentials.twoStepLoginMethod === undefined ||
      body?.two_step_login_method === credentials.twoStepLoginMethod;
    const matchesTwoStepCode =
      credentials.twoStepLoginCode === undefined ||
      body?.two_step_login_code === credentials.twoStepLoginCode;

    let matchesApiKey = true;
    if (credentials.method === 'api_key') {
      matchesApiKey =
        body?.client_id === credentials.clientId &&
        body?.client_secret === credentials.clientSecret;
    }

    if (!matchesMethod || !matchesEmail || !matchesMasterPassword || !matchesApiKey || !matchesTwoStepMethod || !matchesTwoStepCode) {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Invalid credentials' }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: sessionId,
        user_email: credentials.email,
        created_at: createdAt,
        expires_at: expiresAt,
      }),
    });
  });
}

/**
 * Mock catalog data for testing
 */
export async function mockCatalogData(page: Page, customServers?: CatalogMockServer[]) {
  const catalogPayload = registryCatalog as unknown as CatalogFixturePayload;
  const fixtureServers = Array.isArray(catalogPayload)
    ? catalogPayload
    : (catalogPayload.servers ?? []);
  const servers = customServers ?? fixtureServers;

  console.log('Registering catalog mock...');
  await page.route(url => url.toString().includes('/api/catalog'), route => {
    const url = new URL(route.request().url());
    if (url.pathname !== '/api/catalog' && url.pathname !== '/api/catalog/search') {
      route.continue();
      return;
    }
    if (route.request().method() !== 'GET') {
      route.continue();
      return;
    }
    console.log(`MOCK HIT (catalog): ${route.request().url()}`);
    const q = url.searchParams.get('q') || url.searchParams.get('query') || '';
    const category = url.searchParams.get('category') || '';
    const pageParam = Number(url.searchParams.get('page')) || 1;
    const pageSize = Number(url.searchParams.get('page_size')) || 8;

    const filtered = servers.filter((item) => {
      const name = (item.name || '').toLowerCase();
      const description = (item.description || '').toLowerCase();
      const id = (item.id || '').toLowerCase();
      const vendor = (item.vendor || '').toLowerCase();
      const query = q.toLowerCase();
      const matchesQuery =
        q === '' ||
        name.includes(query) ||
        description.includes(query) ||
        id.includes(query) ||
        vendor.includes(query);
      const matchesCategory = category === '' || item.category === category;
      return matchesQuery && matchesCategory;
    });
    const start = (pageParam - 1) * pageSize;
    const paged = filtered.slice(start, start + pageSize);

    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        servers: paged,
        total: filtered.length,
        page: pageParam,
        page_size: pageSize,
        categories: Array.from(new Set(servers.map(s => s.category))),
        cached: false,
      }),
    });
  });
}

/**
 * Mock container list data
 */
export async function mockContainerList(page: Page, containers: any[] = []) {
  console.log('Registering containers mock...');
  await page.route(url => url.toString().includes('/api/containers'), route => {
    console.log(`MOCK HIT (containers): ${route.request().url()}`);
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
  await page.route(url => url.toString().includes(`/api/inspector/${containerId}/capabilities`), route => {
    console.log(`MOCK HIT (inspector capabilities): ${route.request().url()}`);
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        tools: [],
        resources: [],
        prompts: [],
        capabilities: {
          logging: {},
        },
      }),
    });
  });

  // Mock tools
  await page.route(url => url.toString().includes(`/api/inspector/${containerId}/tools`), route => {
    console.log(`MOCK HIT (inspector tools): ${route.request().url()}`);
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  // Mock resources
  await page.route(url => url.toString().includes(`/api/inspector/${containerId}/resources`), route => {
    console.log(`MOCK HIT (inspector resources): ${route.request().url()}`);
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  // Mock prompts
  await page.route(url => url.toString().includes(`/api/inspector/${containerId}/prompts`), route => {
    console.log(`MOCK HIT (inspector prompts): ${route.request().url()}`);
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
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
export async function waitForToast(page: Page, message?: string | RegExp, timeout: number = 8000) {
  // Prefer role="alert" when message is not specified
  if (!message) {
    const toast = page.locator('[role="alert"]').or(page.locator('.toast'));
    await toast.first().waitFor({ state: 'visible', timeout });
    return toast.first();
  }

  const toast = page.getByText(message);
  await toast.first().waitFor({ state: 'visible', timeout });
  return toast.first();
}

/**
 * Mock remote server list response
 */
export async function mockRemoteServers(page: Page, servers: any[]) {
  await page.route('**/api/remote-servers', (route) => {
    if (route.request().method() !== 'GET') {
      route.continue();
      return;
    }
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(servers),
    });
  });
}

/**
 * Mock remote server detail response
 */
export async function mockRemoteServerDetail(page: Page, server: any) {
  await page.route(`**/api/remote-servers/${server.server_id}`, (route) => {
    if (route.request().method() !== 'GET') {
      route.continue();
      return;
    }
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(server),
    });
  });
}

/**
 * Mock start OAuth for remote server
 */
export async function mockStartRemoteOAuth(
  page: Page,
  params: { serverId: string; authUrl: string; state: string; requiredScopes?: string[] }
) {
  await page.route('**/api/oauth/start', async (route) => {
    if (route.request().method() !== 'POST') {
      route.continue();
      return;
    }
    const body = await route.request().postDataJSON();
    if (body?.server_id !== params.serverId) {
      route.fulfill({ status: 404 });
      return;
    }
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        auth_url: params.authUrl,
        state: params.state,
        required_scopes: params.requiredScopes ?? [],
      }),
    });
  });
}

/**
 * Mock remote server test connection response
 */
export async function mockRemoteTest(
  page: Page,
  serverId: string,
  result: { reachable: boolean; authenticated: boolean; capabilities?: any; error?: string | null }
) {
  await page.route(`**/api/remote-servers/${serverId}/test`, (route) => {
    if (route.request().method() !== 'POST') {
      route.continue();
      return;
    }
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        server_id: serverId,
        ...result,
      }),
    });
  });
}
