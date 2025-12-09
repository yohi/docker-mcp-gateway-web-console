# Technology Stack

最終更新: 2025-12-09

## アーキテクチャ

- Next.js (App Router) フロントエンドが FastAPI バックエンドと REST 経由で通信。
- バックエンドは Docker デーモンと Bitwarden CLI を操作し、MCP サーバーの起動・停止やシークレット注入を実行。
- Docker Compose でフロント (既定 3000) / バックエンド (既定 8000) を一括起動可能。

## コア技術

- **言語**: TypeScript、Python 3.11+
- **フレームワーク**: Next.js 14、FastAPI
- **ランタイム**: Node.js 18+、Python 3.11+
- **UI/スタイル**: React 18、Tailwind CSS
- **データフェッチ**: SWR
- **バリデーション**: Pydantic v2
- **コンテナ制御**: docker SDK for Python
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

- フロント: `NEXT_PUBLIC_API_URL`（バックエンド API URL）
- バックエンド: `BITWARDEN_CLI_PATH`, `DOCKER_HOST`, `SESSION_TIMEOUT_MINUTES`, `CATALOG_CACHE_TTL_SECONDS`, `CORS_ORIGINS`, `LOG_LEVEL`, `SECRET_CACHE_TTL_SECONDS`, `MAX_LOG_LINES`, `CATALOG_DEFAULT_URL`
- Compose 用: `FRONTEND_PORT`, `BACKEND_PORT`, `NEXT_PUBLIC_API_URL`

## よく使うコマンド

```bash
# 開発起動 (フロント/バックエンド同時)
docker-compose up

# フロントエンド
cd frontend
npm install
npm run dev        # 開発サーバー
npm test           # ユニット
npm run test:e2e   # E2E (Playwright)

# バックエンド
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```
