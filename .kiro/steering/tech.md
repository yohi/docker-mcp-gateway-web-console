# Technology Stack

最終更新: 2025-12-10

## アーキテクチャ

- Next.js (App Router) フロントエンドが FastAPI バックエンドと REST 経由で通信。
- バックエンドは Docker デーモンと Bitwarden CLI を操作し、MCP サーバーの起動・停止やシークレット注入を実行。
- OAuth カタログ接続をバックエンドで管理し、PKCE/state 生成とトークン暗号化保存を行う。
- セッション情報・外部ゲートウェイ・監査ログを SQLite (`data/state.db`) に保存し、ポリシー・許可リストを参照。
- Docker Compose でフロント (既定 3000) / バックエンド (既定 8000) を一括起動可能。

## コア技術

- **言語**: TypeScript、Python 3.11+
- **フレームワーク**: Next.js 14、FastAPI
- **ランタイム**: Node.js 18+、Python 3.11+
- **UI/スタイル**: React 18、Tailwind CSS
- **データフェッチ**: SWR
- **バリデーション**: Pydantic v2
- **コンテナ制御**: docker SDK for Python
- **HTTP クライアント**: httpx（カタログ/GitHub/OAuth/ゲートウェイヘルスチェック）
- **暗号**: cryptography/Fernet（OAuth トークン暗号化）
- **データストア**: SQLite (state.db) でセッション・ゲートウェイ・資格情報を永続化
- **メトリクス/監査**: MetricsRecorder と監査ログで署名検証・ゲートウェイ許可判定を計測
- **ASGI サーバー**: uvicorn

## テスト

- **フロントエンド**: Jest（ユニット）、Playwright（E2E）、Testing Library
- **バックエンド**: Pytest、Hypothesis、pytest-asyncio

## 開発環境・必須ツール

- Docker Engine / Docker Compose
- Node.js 18+（フロントビルド）
- Python 3.11+（バックエンド）
- Bitwarden CLI (`bw` ログインが前提)

## 主な環境変数

- フロント: `NEXT_PUBLIC_API_URL`（バックエンド API URL）、`NEXT_PUBLIC_CATALOG_URL`（カタログ URL 上書き）
- バックエンド:
  - Bitwarden/Docker: `BITWARDEN_CLI_PATH`, `BITWARDEN_CLI_TIMEOUT_SECONDS`, `DOCKER_HOST`
  - セッション・永続化: `SESSION_TIMEOUT_MINUTES`, `STATE_DB_PATH`, `CREDENTIAL_RETENTION_DAYS`, `JOB_RETENTION_HOURS`, `MTLS_PLACEHOLDER_MODE`
  - カタログ: `CATALOG_CACHE_TTL_SECONDS`, `CATALOG_DEFAULT_URL`, `GITHUB_TOKEN`
  - OAuth: `OAUTH_AUTHORIZE_URL`, `OAUTH_TOKEN_URL`, `OAUTH_CLIENT_ID`, `OAUTH_REDIRECT_URI`, `OAUTH_REQUEST_TIMEOUT_SECONDS`, `OAUTH_TOKEN_ENCRYPTION_KEY`, `OAUTH_TOKEN_ENCRYPTION_KEY_ID`
  - セキュリティ/ログ: `CORS_ORIGINS`, `LOG_LEVEL`, `LOG_REQUEST_BODY`
- Compose 用: `FRONTEND_PORT`, `BACKEND_PORT`, `NEXT_PUBLIC_API_URL`

## よく使うコマンド

```bash
# 開発起動 (フロント/バックエンド同時・リポジトリルートにある docker-compose.yml を使用)
docker compose up

# フロントエンド (frontend/package.json に定義されたスクリプト)
cd frontend
npm install
npm run dev        # 開発サーバー
npm test           # ユニット (Jest)
npm run test:e2e   # E2E (Playwright)

# バックエンド
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```
