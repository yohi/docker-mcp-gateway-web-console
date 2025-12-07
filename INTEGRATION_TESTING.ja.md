[English](INTEGRATION_TESTING.md)

# 統合およびE2Eテストガイド

このドキュメントでは、Docker MCP Gateway Consoleの統合テストおよびエンドツーエンド（E2E）テストに関する包括的な情報を提供します。

## 概要

プロジェクトは多層的なテストアプローチを使用しています：

1. **単体テスト (Unit Tests)**: 個々のコンポーネントと関数を分離してテストします
2. **統合テスト (Integration Tests)**: コンポーネントとサービス間の相互作用をテストします
3. **E2Eテスト (E2E Tests)**: ブラウザからバックエンドまでの完全なユーザーワークフローをテストします

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────┐
│                    E2E Tests (Playwright)                │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │         Browser Automation                       │   │
│  │  - User interactions                             │   │
│  │  - Visual verification                           │   │
│  │  - Network mocking                               │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Frontend (Next.js + React)                  │
│                                                           │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │  Unit Tests      │  │  Component Tests │            │
│  │  (Jest)          │  │  (React Testing) │            │
│  └──────────────────┘  └──────────────────┘            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Backend (FastAPI + Python)                  │
│                                                           │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │  Unit Tests      │  │  Integration     │            │
│  │  (pytest)        │  │  Tests (pytest)  │            │
│  └──────────────────┘  └──────────────────┘            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│         External Services (Docker, Bitwarden)            │
└─────────────────────────────────────────────────────────┘
```

## Playwrightを使用したE2Eテスト

### セットアップ

1. 依存関係のインストール:
```bash
cd frontend
npm install
```

2. Playwrightブラウザのインストール:
```bash
npx playwright install --with-deps
```

### テストの実行

#### ローカル開発

```bash
# アプリケーションの起動
docker-compose up -d

# E2Eテストの実行
cd frontend
npm run test:e2e
```

#### テスト環境を使用

```bash
# テストスクリプトの使用（推奨）
./scripts/run-e2e-tests.sh

# または手動実行
docker-compose -f docker-compose.test.yml up -d frontend backend
cd frontend
npm run test:e2e
```

#### インタラクティブモード

```bash
# UIモード（開発に最適）
npm run test:e2e:ui

# ヘッドレスモード以外（ブラウザを表示）
npm run test:e2e:headed

# デバッグモード
npx playwright test --debug
```

### テスト構造

```
frontend/e2e/
├── auth.spec.ts          # 認証フロー
├── catalog.spec.ts       # カタログ閲覧
├── containers.spec.ts    # コンテナ管理
├── inspector.spec.ts     # MCPインスペクター
├── helpers.ts            # 共有ユーティリティ
└── README.md            # 詳細ドキュメント
```

### E2Eテストの作成

#### 基本的なテスト構造

```typescript
import { test, expect } from '@playwright/test';

test.describe('Feature Name', () => {
  test.beforeEach(async ({ page }) => {
    // Setup before each test
    await page.goto('/');
  });

  test('should do something', async ({ page }) => {
    // Arrange
    await page.getByLabel('Input').fill('value');
    
    // Act
    await page.getByRole('button', { name: 'Submit' }).click();
    
    // Assert
    await expect(page).toHaveURL('/success');
  });
});
```

#### モックの使用

```typescript
import { mockAuthentication, mockCatalogData } from './helpers';

test('should work with mocked data', async ({ page }) => {
  // Mock authentication
  await mockAuthentication(page);
  
  // Mock API responses
  await page.route('**/api/catalog', route => {
    route.fulfill({
      status: 200,
      body: JSON.stringify({ servers: [] })
    });
  });
  
  // Test with mocked data
  await page.goto('/catalog');
});
```

### ベストプラクティス

1. **セマンティックセレクタの使用**
   - ✅ `page.getByRole('button', { name: 'Login' })`
   - ✅ `page.getByLabel('Email')`
   - ❌ `page.locator('.btn-primary')`

2. **状態の待機**
   ```typescript
   await page.waitForLoadState('networkidle');
   await page.waitForURL('/dashboard');
   ```

3. **非同期操作の処理**
   ```typescript
   await expect(page.getByText('Success')).toBeVisible({ timeout: 5000 });
   ```

4. **実装ではなくユーザーフローのテスト**
   - 実装方法ではなく、ユーザーが何をするかに焦点を当てる
   - 開始から終了までの完全なワークフローをテストする

5. **テストの独立性維持**
   - 各テストは分離して実行できる必要がある
   - テスト実行順序に依存しない

## 統合テスト

### バックエンド統合テスト

`backend/tests/` に配置され、以下を検証します：
- APIエンドポイント機能
- サービス層の相互作用
- データベース操作
- 外部サービス統合

#### バックエンドテストの実行

```bash
cd backend
pytest

# カバレッジ付き
pytest --cov=app --cov-report=html

# 特定のテストファイル
pytest tests/test_auth.py

# 特定のテスト
pytest tests/test_auth.py::test_login_success
```

### フロントエンド統合テスト

`frontend/__tests__/` に配置され、以下を検証します：
- コンポーネントの相互作用
- コンテキストプロバイダー
- APIクライアント関数
- フォーム送信

#### フロントエンドテストの実行

```bash
cd frontend
npm test

# ウォッチモード
npm run test:watch

# カバレッジ付き
npm test -- --coverage
```

## Docker Compose設定

### 開発 (`docker-compose.yml`)

- 標準的な開発環境
- ホットリローディング有効
- ポート: 3000 (frontend), 8000 (backend)

### テスト (`docker-compose.test.yml`)

- 分離されたテスト環境
- 競合を避けるための異なるポート
- サービス準備のためのヘルスチェック
- ポート: 3001 (frontend), 8001 (backend)

### 使用法

```bash
# 開発
docker-compose up

# テスト
docker-compose -f docker-compose.test.yml up

# クリーンアップ
docker-compose down -v
docker-compose -f docker-compose.test.yml down -v
```

## CI/CD統合

### GitHub Actions

プロジェクトには以下のGitHub Actionsワークフロー（`.github/workflows/e2e-tests.yml`）が含まれています：

1. Node.jsとPython環境のセットアップ
2. 依存関係のインストール
3. Docker Composeサービスの起動
4. E2Eテストの実行
5. テストレポートとアーティファクトのアップロード
6. 失敗時のログ表示

### CIでの実行

```yaml
# .github/workflows/e2e-tests.yml
- name: Run E2E tests
  run: npm run test:e2e
  env:
    CI: true
    PLAYWRIGHT_BASE_URL: http://localhost:3001
```

## テストデータ管理

### モックデータ

E2Eテストの場合、`frontend/e2e/helpers.ts` のヘルパー関数を使用します：

```typescript
// Mock authentication
await mockAuthentication(page);

// Mock catalog data
await mockCatalogData(page);

// Mock container list
await mockContainerList(page, [
  { id: 'test-1', name: 'test-container', status: 'running' }
]);

// Mock inspector data
await mockInspectorData(page, 'container-id');
```

### テスト資格情報

実際のBitwardenアクセスが必要な統合テストの場合：

1. テスト用Bitwardenアカウントを作成
2. 資格情報を環境変数に保存
3. テストデータ用に別の保管庫を使用
4. 資格情報をリポジトリにコミットしない

```bash
# .env.test
BITWARDEN_TEST_EMAIL=test@example.com
BITWARDEN_TEST_API_KEY=test-api-key
```

## デバッグ

### Playwrightデバッグ

```bash
# UIモード（インタラクティブ）
npm run test:e2e:ui

# デバッグモード（ステップ実行）
npx playwright test --debug

# デバッグモードでの特定テスト
npx playwright test auth.spec.ts --debug

# ブラウザ表示
npm run test:e2e:headed
```

### テストレポートの表示

```bash
# テスト実行後
npx playwright show-report

# 特定のレポートを開く
npx playwright show-report playwright-report/
```

### 失敗の分析

1. **スクリーンショット**: 失敗時に自動キャプチャ
2. **トレース**: 初回リトライ時にキャプチャ
3. **ビデオ**: オプション、`playwright.config.ts` で設定
4. **ログ**: Docker Composeログを確認

```bash
# ログ表示
docker-compose -f docker-compose.test.yml logs backend
docker-compose -f docker-compose.test.yml logs frontend

# ログ追跡
docker-compose -f docker-compose.test.yml logs -f
```

## パフォーマンステスト

### 負荷テスト

負荷テストには、以下を検討してください：
- [k6](https://k6.io/) API負荷テスト用
- [Lighthouse](https://developers.google.com/web/tools/lighthouse) フロントエンドパフォーマンス用

### k6スクリプト例

```javascript
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  vus: 10,
  duration: '30s',
};

export default function() {
  let res = http.get('http://localhost:8000/api/catalog?source=test');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
}
```

## トラブルシューティング

### 一般的な問題

#### ローカルでのテスト失敗

1. **ポート競合**: ポート 3000/8000 が使用中でないか確認
2. **古いコンテナ**: `docker-compose down -v` を実行
3. **ブラウザの問題**: `npx playwright install` を実行
4. **キャッシュの問題**: `.next` と `node_modules` をクリア

#### 不安定なテスト

1. 明示的な待機を追加: `waitForLoadState('networkidle')`
2. タイムアウトを増やす: `{ timeout: 10000 }`
3. 競合状態を確認
4. 設定でリトライロジックを使用

#### CIでの失敗

1. GitHub Actionsログを確認
2. テストアーティファクトをダウンロード
3. スクリーンショットとトレースをレビュー
4. 環境変数を確認

### ヘルプを得る

1. [Playwrightドキュメント](https://playwright.dev)を確認
2. テストログとレポートを確認
3. Docker Composeログを確認
4. 以下を含めてIssueを作成：
   - テスト出力
   - スクリーンショット/トレース
   - 環境詳細

## メンテナンス

### 依存関係の更新

```bash
# フロントエンド
cd frontend
npm update
npx playwright install

# バックエンド
cd backend
pip install --upgrade -r requirements.txt
```

### テストの更新

新機能を追加する場合：

1. ユーザーワークフローのE2Eテストを作成
2. APIエンドポイントの統合テストを作成
3. ビジネスロジックの単体テストを作成
4. テストドキュメントを更新

### テストカバレッジ目標

- 単体テスト: 80%以上のカバレッジ
- 統合テスト: 主要なワークフローをカバー
- E2Eテスト: 重要なユーザーパスをカバー

## リソース

- [Playwright Documentation](https://playwright.dev)
- [Jest Documentation](https://jestjs.io)
- [pytest Documentation](https://docs.pytest.org)
- [Docker Compose Documentation](https://docs.docker.com/compose)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
