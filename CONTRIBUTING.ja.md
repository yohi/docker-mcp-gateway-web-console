[English](CONTRIBUTING.md)

# Docker MCP Gateway Console への貢献

貢献にご関心をお寄せいただきありがとうございます！このドキュメントでは、プロジェクトに貢献するためのガイドラインと手順を提供します。

## 目次

- [行動規範](#行動規範)
- [はじめに](#はじめに)
- [開発セットアップ](#開発セットアップ)
- [変更の実施](#変更の実施)
- [テスト](#テスト)
- [変更の送信](#変更の送信)
- [コーディング規約](#コーディング規約)
- [ドキュメント](#ドキュメント)

## 行動規範

このプロジェクトは行動規範を遵守します。参加することにより、この規範を守ることが期待されます。容認できない行動については、プロジェクトメンテナに報告してください。

### 私たちの基準

- 敬意を払い、包括的であること
- 新規参加者を歓迎し、学習を支援すること
- コミュニティにとって最善のことに焦点を当てること
- 他のコミュニティメンバーに対して共感を示すこと

## はじめに

### 前提条件

貢献する前に、以下を確認してください：

- Git がインストールされていること
- Node.js 18+ がインストールされていること
- Python 3.11+ がインストールされていること
- Docker および Docker Compose がインストールされていること
- Bitwarden CLI がインストールされていること
- テスト用の Bitwarden アカウント

### 取り組む課題を見つける

1. [Issues](repository-url/issues) ページを確認します
2. `good first issue` または `help wanted` ラベルの付いた課題を探します
3. 他の人に取り組んでいることを知らせるために、課題にコメントします
4. 作業を開始する前にメンテナの承認を待ちます

### バグの報告

バグ報告を作成する前に：

1. バグが既に報告されていないか確認します
2. 関連情報（ログ、スクリーンショット、再現手順）を収集します
3. 以下を含む詳細なIssueを作成します：
   - 明確なタイトル
   - バグの説明
   - 再現手順
   - 期待される動作
   - 実際の動作
   - 環境の詳細（OS、バージョンなど）

### 機能の提案

機能のリクエストは大歓迎です！以下をお願いします：

1. 機能が既にリクエストされていないか確認します
2. 機能とその利点を明確に説明します
3. どのように使用されるかの例を提供します
4. 議論やフィードバックを受け入れます

## 開発セットアップ

### 1. フォークとクローン

```bash
# GitHubでリポジトリをフォークしてから：
git clone https://github.com/YOUR-USERNAME/docker-mcp-gateway-console.git
cd docker-mcp-gateway-console

# アップストリームリモートを追加
git remote add upstream https://github.com/ORIGINAL-OWNER/docker-mcp-gateway-console.git
```

### 2. 依存関係のインストール

```bash
# バックエンド
cd backend
python -m venv venv
source venv/bin/activate  # Windowsの場合: venv\Scripts\activate
pip install -r requirements.txt
cd ..

# フロントエンド
cd frontend
npm install
cd ..
```

### 3. 環境のセットアップ

```bash
# 環境ファイルのコピー
cp frontend/.env.local.example frontend/.env.local
cp backend/.env.example backend/.env

# ローカル設定に合わせて編集
```

### 4. 開発環境の起動

```bash
# オプション 1: Docker Composeを使用
docker-compose up

# オプション 2: サービスを個別に実行
# ターミナル 1 - バックエンド
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

# ターミナル 2 - フロントエンド
cd frontend
npm run dev
```

## 変更の実施

### ブランチの命名

説明的なブランチ名を使用してください：

- `feature/add-new-catalog-filter`
- `fix/session-timeout-bug`
- `docs/update-deployment-guide`
- `refactor/improve-secret-caching`

### コミットメッセージ

Conventional Commit 形式に従ってください：

```
type(scope): subject

body (optional)

footer (optional)
```

**タイプ:**
- `feat`: 新機能
- `fix`: バグ修正
- `docs`: ドキュメント変更
- `style`: コードスタイル変更（フォーマットなど）
- `refactor`: コードリファクタリング
- `test`: テストの追加または更新
- `chore`: メンテナンス作業

**例:**
```
feat(catalog): add category filtering

Add ability to filter catalog items by multiple categories
simultaneously. Updates the search bar component and catalog
service.

Closes #123
```

```
fix(auth): resolve session timeout issue

Sessions were not properly expiring after the configured timeout.
Fixed by updating the session validation logic.

Fixes #456
```

### 変更の実施

1. **ブランチを作成:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **変更を行う:**
   - クリーンで読みやすいコードを書く
   - 既存のコードスタイルに従う
   - 複雑なロジックにはコメントを追加する
   - 必要に応じてドキュメントを更新する

3. **変更をテストする:**
   - すべてのテストを実行する
   - UIで手動テストを行う
   - リグレッションがないことを確認する

4. **変更をコミットする:**
   ```bash
   git add .
   git commit -m "feat(scope): your message"
   ```

## テスト

### テストの実行

```bash
# バックエンドテスト
cd backend
pytest

# フロントエンド単体テスト
cd frontend
npm test

# フロントエンドE2Eテスト
cd frontend
npm run test:e2e

# すべてのテストを実行
npm run test:all  # 利用可能な場合
```

### テストの作成

#### バックエンドテスト (pytest)

```python
# backend/tests/test_feature.py
import pytest
from app.services.feature import FeatureService

def test_feature_functionality():
    """Test that feature works correctly"""
    service = FeatureService()
    result = service.do_something()
    assert result == expected_value
```

#### フロントエンド単体テスト (Jest)

```typescript
// frontend/__tests__/components/Feature.test.tsx
import { render, screen } from '@testing-library/react';
import Feature from '@/components/Feature';

describe('Feature', () => {
  it('renders correctly', () => {
    render(<Feature />);
    expect(screen.getByText('Expected Text')).toBeInTheDocument();
  });
});
```

#### E2Eテスト (Playwright)

```typescript
// frontend/e2e/feature.spec.ts
import { test, expect } from '@playwright/test';

test('feature workflow', async ({ page }) => {
  await page.goto('/');
  await page.click('button[data-testid="feature-button"]');
  await expect(page.locator('.result')).toBeVisible();
});
```

### テストカバレッジ

- 少なくとも80%のコードカバレッジを目指してください
- すべての新機能にはテストを含める必要があります
- バグ修正にはリグレッションテストを含める必要があります

## 変更の送信

### プルリクエストプロセス

1. **ブランチを更新:**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **フォークへプッシュ:**
   ```bash
   git push origin feature/your-feature-name
   ```

3. **プルリクエストを作成:**
   - GitHubへ行きPRを作成
   - PRテンプレートに記入
   - 関連するIssueをリンク
   - メンテナにレビューを依頼

### プルリクエストテンプレート

```markdown
## Description
変更の簡潔な説明

## Type of Change
- [ ] Bug fix (バグ修正)
- [ ] New feature (新機能)
- [ ] Breaking change (破壊的変更)
- [ ] Documentation update (ドキュメント更新)

## Testing
- [ ] Unit tests pass (単体テスト通過)
- [ ] E2E tests pass (E2Eテスト通過)
- [ ] Manual testing completed (手動テスト完了)

## Checklist
- [ ] Code follows project style guidelines (コードスタイルガイドラインに従っている)
- [ ] Self-review completed (自己レビュー完了)
- [ ] Comments added for complex code (複雑なコードにコメント追加)
- [ ] Documentation updated (ドキュメント更新)
- [ ] No new warnings generated (新たな警告が発生していない)
- [ ] Tests added/updated (テスト追加/更新)
```

### レビュープロセス

1. メンテナがPRをレビューします
2. フィードバックや変更要求に対応します
3. 承認されると、PRはマージされます
4. あなたの貢献がクレジットされます

## コーディング規約

### Python (バックエンド)

- PEP 8 スタイルガイドに従う
- 型ヒントを使用する
- 最大行長: 100文字
- 意味のある変数名を使用する
- 関数とクラスにdocstringを追加する

```python
from typing import Optional

def process_secret(secret_ref: str, session_id: str) -> Optional[str]:
    """
    Process a Bitwarden secret reference.
    
    Args:
        secret_ref: Bitwarden reference notation
        session_id: User session identifier
        
    Returns:
        Resolved secret value or None if not found
    """
    # Implementation
    pass
```

### TypeScript (フロントエンド)

- TypeScript strictモードを使用する
- Airbnbスタイルガイドに従う
- フックを使用した関数コンポーネントを使用する
- letよりもconstを優先する
- 意味のある変数名を使用する

```typescript
interface ContainerConfig {
  name: string;
  image: string;
  env: Record<string, string>;
}

const createContainer = async (config: ContainerConfig): Promise<string> => {
  // Implementation
  return containerId;
};
```

### コードフォーマット

```bash
# バックエンド (Black)
cd backend
black app/ tests/

# フロントエンド (Prettier)
cd frontend
npm run format
```

### リンティング

```bash
# バックエンド (Flake8)
cd backend
flake8 app/ tests/

# フロントエンド (ESLint)
cd frontend
npm run lint
```

## ドキュメント

### コードドキュメント

- 複雑なロジックにコメントを追加する
- Python関数にはdocstringを使用する
- TypeScript関数にはJSDocを使用する
- コメントを最新の状態に保つ

### ユーザードキュメント

機能を追加する際は以下を更新してください：

- README.ja.md
- `docs/` ディレクトリ内の関連ドキュメント
- APIドキュメント（該当する場合）
- UI内のインラインヘルプテキスト

### ドキュメントスタイル

- 明確で簡潔な言葉を使用する
- コード例を含める
- UI機能のスクリーンショットを追加する
- フォーマットの一貫性を保つ

## プロジェクト構造

```
docker-mcp-gateway-console/
├── backend/              # Python FastAPI バックエンド
│   ├── app/
│   │   ├── api/         # API エンドポイント
│   │   ├── models/      # データモデル
│   │   ├── services/    # ビジネスロジック
│   │   └── main.py      # アプリケーションエントリ
│   └── tests/           # バックエンドテスト
├── frontend/            # Next.js フロントエンド
│   ├── app/            # Next.js ページ
│   ├── components/     # React コンポーネント
│   ├── lib/            # ユーティリティ
│   └── __tests__/      # フロントエンドテスト
├── docs/               # ドキュメント
└── docker-compose.yml  # 開発環境
```

## ヘルプを得る

- **質問**: GitHubでディスカッションを開く
- **問題**: 詳細を記載してIssueを作成する
- **チャット**: コミュニティチャットに参加する（利用可能な場合）
- **メール**: メンテナに連絡する（提供されている場合）

## 表彰

貢献者は以下のように扱われます：

- CONTRIBUTORS.md に記載
- リリースノートでクレジット
- プロジェクトドキュメントで言及

## ライセンス

貢献することにより、あなたの貢献がプロジェクトと同じライセンスの下でライセンスされることに同意したことになります。

## ありがとう！

あなたの貢献はこのプロジェクトを誰にとってもより良いものにします。あなたの時間と労力に感謝します！
