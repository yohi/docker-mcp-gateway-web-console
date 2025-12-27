[English](ENVIRONMENT_VARIABLES.md)

# 環境変数

このドキュメントでは、Docker MCP Gateway Consoleで使用されるすべての環境変数について説明します。

## フロントエンド環境変数

`frontend/` ディレクトリに `.env.local` ファイルを作成します：

### 必須変数

| 変数 | 説明 | デフォルト | 例 |
|----------|-------------|---------|---------|
| `NEXT_PUBLIC_API_URL` | バックエンドAPI URL | `http://localhost:8000` | `https://api.example.com` |

### `.env.local` の例

```env
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## バックエンド環境変数

`backend/` ディレクトリに `.env` ファイルを作成します：

### 必須変数

| 変数 | 説明 | デフォルト | 例 |
|----------|-------------|---------|---------|
| `BITWARDEN_CLI_PATH` | Bitwarden CLI実行ファイルへのパス | `/usr/local/bin/bw` | `/usr/bin/bw` |
| `DOCKER_HOST` | Dockerデーモンソケット | `unix:///var/run/docker.sock` | `tcp://localhost:2375` |
| `DOCKER_SOCKET_PATH` | Dockerソケットの実ファイルパス（`unix://`指定時） | `/var/run/docker.sock` | `/run/user/1000/docker.sock` |

### オプション変数

| 変数 | 説明 | デフォルト | 例 |
|----------|-------------|---------|---------|
| `SESSION_TIMEOUT_MINUTES` | セッション非アクティブタイムアウト | `30` | `60` |
| `CATALOG_CACHE_TTL_SECONDS` | カタログキャッシュの生存時間 | `3600` | `7200` |
| `CORS_ORIGINS` | 許可されるCORSオリジン（カンマ区切り） | `http://localhost:3000` | `https://app.example.com,https://admin.example.com` |
| `LOG_LEVEL` | ログレベル | `INFO` | `DEBUG`, `WARNING`, `ERROR` |
| `SECRET_CACHE_TTL_SECONDS` | シークレットキャッシュの生存時間 | `1800` | `3600` |
| `MAX_LOG_LINES` | ストリーミングする最大ログ行数 | `1000` | `5000` |
| `CATALOG_OFFICIAL_URL` | Official MCP Registry URL | `https://registry.modelcontextprotocol.io/v0/servers` | `https://registry.example.com/v0/servers` |
| `CATALOG_OFFICIAL_MAX_PAGES` | Official Registry からの最大取得ページ数（1ページ=30件） | `20` | `50` |
| `CATALOG_OFFICIAL_FETCH_TIMEOUT` | 全ページ取得の合計タイムアウト秒数 | `60` | `120` |
| `CATALOG_OFFICIAL_PAGE_DELAY` | ページ間遅延ミリ秒 | `100` | `200` |
| `CATALOG_DOCKER_URL` | Docker MCP Catalog URL (`CATALOG_DEFAULT_URL` 推奨代替) | `CATALOG_DEFAULT_URL` の値 | `https://example.com/docker_catalog.json` |
| `CATALOG_DEFAULT_URL` | デフォルトのカタログURL (**非推奨**) | - | `https://example.com/catalog.json` |
| `REMOTE_MCP_ALLOWED_DOMAINS` | 許可するリモートMCPサーバーのドメイン（カンマ区切り）。空の場合はすべて拒否。 | `""` | `api.example.com,*.trusted.com` |
| `REMOTE_MCP_MAX_CONNECTIONS` | リモートサーバーへの最大同時SSE接続数 | `20` | `5` |
| `ALLOW_INSECURE_ENDPOINT` | HTTP/localhost エンドポイントを許可（開発環境のみ） | `false` | `true` |

**注意**: カタログ URL 設定の移行については [移行ガイド](migrations/mcp-registry-source-selector.md) を参照してください。

### `.env` の例

```env
# Bitwarden Configuration
BITWARDEN_CLI_PATH=/usr/local/bin/bw

# Docker Configuration
DOCKER_HOST=unix:///var/run/docker.sock
# ルートレス Docker 等、ソケットパスが異なる場合に上書き
# DOCKER_SOCKET_PATH=/run/user/1000/docker.sock

# Session Management
SESSION_TIMEOUT_MINUTES=30

# Catalog Configuration
CATALOG_CACHE_TTL_SECONDS=3600
# Docker Catalog (旧 CATALOG_DEFAULT_URL)
# 推奨: 新しい CATALOG_DOCKER_URL を使用してください
CATALOG_DOCKER_URL=https://raw.githubusercontent.com/example/mcp-catalog/main/catalog.json
# 後方互換性のため当面は CATALOG_DEFAULT_URL も有効ですが、非推奨です
# CATALOG_DEFAULT_URL=...

# Official Registry
CATALOG_OFFICIAL_URL=https://registry.modelcontextprotocol.io/v0/servers
CATALOG_OFFICIAL_MAX_PAGES=20
CATALOG_OFFICIAL_FETCH_TIMEOUT=60
CATALOG_OFFICIAL_PAGE_DELAY=100

# Remote MCP Configuration
REMOTE_MCP_ALLOWED_DOMAINS=api.example.com,*.trusted.com
REMOTE_MCP_MAX_CONNECTIONS=20
ALLOW_INSECURE_ENDPOINT=false

# Security
CORS_ORIGINS=http://localhost:3000

# Logging
LOG_LEVEL=INFO

# Performance
SECRET_CACHE_TTL_SECONDS=1800
MAX_LOG_LINES=1000
```

## Docker Compose 環境変数

Docker Composeを使用する場合、プロジェクトルートの `.env` ファイルでこれらの変数をオーバーライドできます：

```env
# Frontend
FRONTEND_PORT=3000
NEXT_PUBLIC_API_URL=http://localhost:8000

# Backend
BACKEND_PORT=8000
BITWARDEN_CLI_PATH=/usr/local/bin/bw
DOCKER_HOST=unix://${DOCKER_SOCKET_PATH:-/var/run/docker.sock}
DOCKER_SOCKET_PATH=/var/run/docker.sock
SESSION_TIMEOUT_MINUTES=30
LOG_LEVEL=INFO
```

ルートレス Docker や別ユーザーで動作するデーモンに接続する場合は、
`DOCKER_SOCKET_PATH` を実際のソケットパス（例: `/run/user/1000/docker.sock`）に
合わせてください。Compose 側のボリュームマウントも同じパスに自動で切り替わります。

## 本番環境の考慮事項

### セキュリティ

1. **HTTPSの使用**: 本番環境では常にHTTPSを使用してください
   ```env
   NEXT_PUBLIC_API_URL=https://api.yourdomain.com
   ```

2. **CORSの制限**: CORSオリジンを本番ドメインに制限してください
   ```env
   CORS_ORIGINS=https://yourdomain.com
   ```

3. **Dockerソケットの保護**: TLS経由でのDockerの使用を検討してください
   ```env
   DOCKER_HOST=tcp://docker-host:2376
   DOCKER_TLS_VERIFY=1
   DOCKER_CERT_PATH=/path/to/certs
   ```

### パフォーマンス

1. **キャッシュTTLの調整**: パフォーマンス向上のためキャッシュ期間を延ばしてください
   ```env
   CATALOG_CACHE_TTL_SECONDS=7200
   SECRET_CACHE_TTL_SECONDS=3600
   ```

2. **ログの最適化**: 適切なログレベルを使用してください
   ```env
   LOG_LEVEL=WARNING  # 本番環境では詳細度を下げる
   ```

### 監視

1. **デバッグログの有効化**（トラブルシューティング用）:
   ```env
   LOG_LEVEL=DEBUG
   ```

2. **ログ保持の増加**:
   ```env
   MAX_LOG_LINES=5000
   ```

## 環境別設定

### 開発（Development）

```env
LOG_LEVEL=DEBUG
SESSION_TIMEOUT_MINUTES=60
CATALOG_CACHE_TTL_SECONDS=300
```

### ステージング（Staging）

```env
LOG_LEVEL=INFO
SESSION_TIMEOUT_MINUTES=30
CATALOG_CACHE_TTL_SECONDS=1800
CORS_ORIGINS=https://staging.yourdomain.com
```

### 本番（Production）

```env
LOG_LEVEL=WARNING
SESSION_TIMEOUT_MINUTES=30
CATALOG_CACHE_TTL_SECONDS=3600
CORS_ORIGINS=https://yourdomain.com
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

## バリデーション

バックエンドは起動時に環境変数を検証します。必須変数が欠落しているか無効な場合、アプリケーションは対応が必要な変数を示すエラーメッセージとともに起動に失敗します。

## シークレット管理

**重要**: `.env` ファイルは絶対にバージョン管理システムにコミットしないでください。常にテンプレートとして `.env.example` ファイルを使用してください。

`.gitignore` に追加：
```
.env
.env.local
.env.*.local
```
