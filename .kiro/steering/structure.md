# Project Structure

最終更新: 2025-12-18

## 組織方針

フロントエンド (UI/操作) とバックエンド (Docker 制御・認証) を分離し、サービス層にロジックを集約する。

## ディレクトリパターン

### Frontend Application
**Location**: `/frontend/` — Next.js 14 (App Router)
- `app/`: ルーティング、ページ、レイアウト
- `components/`: 再利用 UI コンポーネント（カタログ/OAuth モーダル、GitHub トークン設定、セッション実行パネル等）
- `lib/`: API クライアント・型・バリデータ
- `contexts/`: セッション/トーストなどのコンテキスト
- `hooks/`: Docker コンテナやインストールフローのフック
- `e2e/`, `__tests__/`: Playwright/Jest テスト
- `public/`, `tailwind.config.ts`, `tsconfig.json`: アセット・ビルド設定

### Backend Application
**Location**: `/backend/` — FastAPI + Docker SDK
- `app/api/`: ルートハンドラー（認証、カタログ、GitHub トークン、コンテナ、インスペクタ、OAuth コールバック、ゲートウェイ、リモートMCP、セッション）
- `app/services/`: コアロジック（Docker 操作、秘密管理、カタログ取得、GitHub トークン管理、OAuth フロー、セッション実行と mTLS バンドル生成、署名検証ポリシー適用、外部/E2B ゲートウェイ許可リストとヘルスチェック、リモートMCP接続、監査メトリクス、state ストア）
- `app/models/`: Pydantic モデル（設定、カタログ、GitHub トークン、署名ポリシー、状態記録）
- `app/schemas/`: カタログ関連スキーマ
- `data/`: SQLite `state.db`（セッション・ゲートウェイ・資格情報・トークン）と証明書生成先ディレクトリ。**デフォルトで正規の保存場所**（STATE_DB_PATH 環境変数で上書き可能）
- `tests/`: Pytest ベースの検証（API/プロパティ/署名/ゲートウェイ/状態ストア）

### Docs / Ops
- `docs/`: アーキテクチャ、環境変数、デプロイ、FAQ など
- `scripts/`: E2E セットアップや検証スクリプト
- `.kiro/specs/`: 要件・設計・タスク
- `.kiro/steering/`: ステアリング (本ファイル群)
- `docker-compose*.yml`, `.env.example`: 起動テンプレートと環境例
- `/data/`: ルート直下の state.db（開発時やコンテナセットアップで一時的に生成される可能性があるが、本番では使用しない。backend/data/ が正規パス）

## 命名規約

- **React コンポーネント**: PascalCase (例: `ServerCard.tsx`)
- **Python モジュール**: snake_case (例: `docker_service.py`)
- **API ルート**: ケバブケースのパスでリソースごとに整理

## インポート指針

- **Frontend**: ルート相対エイリアス `@/` を優先。
- **Backend**: `app.` からの絶対インポートを基本とし、サービス層経由で利用。

## コード設計原則

- **サービス層集中**: ビジネスロジックは `services/` に集約し、API 層は薄く保つ。
- **シークレット安全性**: ディスク保存を避け、環境変数または Bitwarden から動的注入し、OAuth/GitHub トークンは Fernet で暗号化。
- **許可リスト・署名検証**: 外部ゲートウェイは許可リスト検証＋定期ヘルスチェック、MCP イメージは署名検証ポリシーで強制/監査を選択。
- **テスト容易性**: API/サービス単位で Pytest、UI/E2E は Jest/Playwright で検証。
