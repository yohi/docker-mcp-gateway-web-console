import { test, expect } from '@playwright/test';
import {
  mockAuthentication,
  mockRemoteServerDetail,
  mockRemoteServers,
  mockRemoteTest,
  mockStartRemoteOAuth,
} from './helpers';

const servers = [
  {
    server_id: 'srv-1',
    catalog_item_id: 'cat-1',
    name: 'Alpha Remote',
    endpoint: 'https://alpha.example.com/sse',
    status: 'auth_required',
    created_at: new Date().toISOString(),
  },
  {
    server_id: 'srv-2',
    catalog_item_id: 'cat-2',
    name: 'Beta Remote',
    endpoint: 'https://beta.example.com/sse',
    status: 'authenticated',
    created_at: new Date().toISOString(),
  },
];

test.describe('Remote Servers', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthentication(page);

    // OAuth リダイレクトをスタブ化（すべてのナビゲーション前に実行）
    await page.addInitScript(() => {
      (window as any).__oauthRedirect = (url: string) => {
        (window as any).__oauthRedirect = url;
      };
    });

    await mockRemoteServers(page, servers);
    await mockRemoteServerDetail(page, servers[0]);
    await mockRemoteServerDetail(page, servers[1]);
  });

  test('リモートサーバー一覧を表示し、詳細・認証・接続テストが行える', async ({ page }) => {
    await page.goto('/remote-servers');

    await expect(page.getByRole('heading', { name: 'リモートサーバー' })).toBeVisible();
    await expect(page.getByTestId('remote-server-row')).toHaveCount(2);
    await expect(page.getByText('Alpha Remote')).toBeVisible();
    await expect(page.getByText('Beta Remote')).toBeVisible();

    // 行をクリックして詳細を表示
    await page.getByTestId('remote-server-row').first().click();
    await expect(page.getByRole('button', { name: '認証開始' })).toBeVisible();

    // OAuth 開始をモック
    await mockStartRemoteOAuth(page, {
      serverId: 'srv-1',
      authUrl: 'https://auth.example.com/authorize',
      state: 'state-123',
    });

    await page.getByRole('button', { name: '認証開始' }).click();

    await expect(async () => {
      const redirect = await page.evaluate(() => (window as any).__oauthRedirect);
      expect(redirect).toBe('https://auth.example.com/authorize');
    }).toPass();

    const stored = await page.evaluate(() => sessionStorage.getItem('oauth:pkce:state-123'));
    expect(stored).not.toBeNull();

    // 接続テストをモック
    await mockRemoteTest(page, 'srv-1', {
      reachable: true,
      authenticated: true,
      capabilities: { tools: ['test'] },
    });

    await page.getByRole('button', { name: '接続テスト' }).click();

    await expect(page.getByText('接続テスト結果')).toBeVisible();
    await expect(page.getByText('到達性: OK')).toBeVisible();
    await expect(page.getByText('認証: 認証済み')).toBeVisible();
  });
});
