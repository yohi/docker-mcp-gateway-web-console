# Project Structure

最終更新: 2025-12-09

## 組織方針

フロントエンド (UI/操作) とバックエンド (Docker 制御・認証) を分離し、サービス層にロジックを集約する。

## ディレクトリパターン

### Frontend Application
**Location**: `/frontend/` — Next.js 14 (App Router)
- `app/`: ルーティング、ページ、レイアウト
- `components/`: 再利用 UI コンポーネント
- `lib/`: フック・ユーティリティ
- `public/`, `tailwind.config.js`, `tsconfig.json`: アセット・ビルド設定

### Backend Application
**Location**: `/backend/` — FastAPI + Docker SDK
- `app/api/`: ルートハンドラー
- `app/services/`: コアロジック（Docker 操作、認証、カタログ、シークレット）
- `app/models/`: Pydantic モデル
- `app/schemas/`: カタログ関連スキーマ
- `tests/`: Pytest ベースの検証

### Docs / Ops
- `docs/`: アーキテクチャ、環境変数、デプロイ、FAQ など
- `scripts/`: E2E セットアップや検証スクリプト
- `.kiro/specs/`: 要件・設計・タスク
- `.kiro/steering/`: ステアリング (本ファイル群)
- `docker-compose*.yml`, `.env.example`: 起動テンプレートと環境例

## 命名規約

- **React コンポーネント**: PascalCase (例: `ServerCard.tsx`)
- **Python モジュール**: snake_case (例: `docker_service.py`)
- **API ルート**: ケバブケースのパスでリソースごとに整理

## インポート指針

- **Frontend**: ルート相対エイリアス `@/` を優先。
- **Backend**: `app.` からの絶対インポートを基本とし、サービス層経由で利用。

## コード設計原則

- **サービス層集中**: ビジネスロジックは `services/` に集約し、API 層は薄く保つ。
- **シークレット安全性**: ディスク保存を避け、環境変数または Bitwarden から動的注入。
- **テスト容易性**: API/サービス単位で Pytest、UI/E2E は Jest/Playwright で検証。
