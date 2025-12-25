[English](CATALOG_SCHEMA.md)

# カタログスキーマドキュメント

このドキュメントでは、Docker MCP Gateway Consoleで使用されるMCPサーバーカタログのスキーマについて説明します。

## 概要

カタログは、利用可能なMCPサーバーとその設定詳細をリストしたJSONファイルです。コンソールはこのカタログを取得し、インストール可能なサーバーを表示します。

## スキーマバージョン

現在のバージョン: `1.0`

## ルートオブジェクト

```json
{
  "version": "1.0",
  "metadata": { ... },
  "servers": [ ... ],
  "categories": [ ... ]
}
```

### フィールド

| フィールド | 型 | 必須 | 説明 |
|-------|------|----------|-------------|
| `version` | string | はい | スキーマバージョン（現在は "1.0"） |
| `metadata` | object | いいえ | カタログメタデータ |
| `servers` | array | はい | サーバー定義の配列 |
| `categories` | array | いいえ | カテゴリ定義の配列 |

## メタデータオブジェクト

```json
{
  "name": "My MCP Catalog",
  "description": "A collection of MCP servers",
  "maintainer": "Your Name",
  "last_updated": "2024-01-01T00:00:00Z"
}
```

### フィールド

| フィールド | 型 | 必須 | 説明 |
|-------|------|----------|-------------|
| `name` | string | いいえ | カタログ名 |
| `description` | string | いいえ | カタログの説明 |
| `maintainer` | string | いいえ | メンテナの名前または組織 |
| `last_updated` | string | いいえ | 最終更新のISO 8601タイムスタンプ |

## サーバーオブジェクト

```json
{
  "id": "mcp-server-example",
  "name": "Example MCP Server",
  "description": "An example server",
  "category": "utilities",
  "docker_image": "example/mcp-server:latest",
  "default_env": {
    "PORT": "8080",
    "API_KEY": "{{ bw:item-id:field }}"
  },
  "required_secrets": ["API_KEY"],
  "documentation_url": "https://github.com/example/mcp-server",
  "tags": ["example", "demo"]
}
```

### フィールド

| フィールド | 型 | 必須 | 説明 |
|-------|------|----------|-------------|
| `id` | string | はい | 一意の識別子（ケバブケース推奨） |
| `name` | string | はい | 表示名 |
| `description` | string | はい | 機能の簡単な説明 |
| `category` | string | はい | カテゴリID（`categories`配列内のカテゴリと一致する必要あり） |
| `docker_image` | string | はい | タグ付きDockerイメージ名 |
| `default_env` | object | いいえ | デフォルト環境変数 |
| `required_secrets` | array | いいえ | シークレットを必要とする環境変数名のリスト |
| `documentation_url` | string | いいえ | ドキュメントへのURL |
| `tags` | array | いいえ | 検索可能なタグの配列 |
| `ports` | object | いいえ | ポートマッピング（下記参照） |
| `volumes` | object | いいえ | ボリュームマッピング（下記参照） |
| `labels` | object | いいえ | Dockerラベル |

### 環境変数

`default_env` 内の環境変数はBitwarden参照記法を使用できます：

```json
{
  "API_KEY": "{{ bw:item-id:field }}",
  "STATIC_VALUE": "some-value"
}
```

**Bitwarden参照形式:**
- `{{ bw:item-id:field }}`
- `item-id`: BitwardenアイテムUUID
- `field`: フィールド名（password, username, またはカスタムフィールド名）

### Portsオブジェクト

```json
{
  "ports": {
    "8080/tcp": 8080,
    "9090/tcp": 9090
  }
}
```

コンテナポートをホストポートにマッピングします。

### Volumesオブジェクト

```json
{
  "volumes": {
    "/data": "/host/path/data",
    "/config": "/host/path/config"
  }
}
```

コンテナパスをホストパスにマッピングします。

## カテゴリオブジェクト

```json
{
  "id": "utilities",
  "name": "Utilities",
  "description": "General-purpose utility servers"
}
```

### フィールド

| フィールド | 型 | 必須 | 説明 |
|-------|------|----------|-------------|
| `id` | string | はい | 一意の識別子（ケバブケース推奨） |
| `name` | string | はい | 表示名 |
| `description` | string | いいえ | カテゴリの説明 |

## 標準カテゴリ

推奨されるカテゴリID:

- `utilities` - 汎用ユーティリティ
- `development` - 開発ツール
- `communication` - メッセージングとコミュニケーション
- `database` - データベース管理
- `ai` - AIと機械学習
- `cloud` - クラウドサービス
- `payments` - 決済処理
- `project-management` - プロジェクト管理
- `productivity` - 生産性向上ツール
- `security` - セキュリティツール
- `monitoring` - 監視と可観測性
- `testing` - テストツール

## 完全な例

```json
{
  "version": "1.0",
  "metadata": {
    "name": "Example MCP Catalog",
    "description": "A sample catalog",
    "maintainer": "Example Org",
    "last_updated": "2024-01-01T00:00:00Z"
  },
  "servers": [
    {
      "id": "mcp-server-github",
      "name": "GitHub MCP Server",
      "description": "Interact with GitHub repositories and issues",
      "category": "development",
      "docker_image": "mcp/github:latest",
      "default_env": {
        "PORT": "8080",
        "GITHUB_TOKEN": "{{ bw:github-token:token }}",
        "GITHUB_API_URL": "https://api.github.com"
      },
      "required_secrets": ["GITHUB_TOKEN"],
      "documentation_url": "https://github.com/example/mcp-github",
      "tags": ["github", "git", "version-control"],
      "ports": {
        "8080/tcp": 8080
      }
    },
    {
      "id": "mcp-server-postgres",
      "name": "PostgreSQL MCP Server",
      "description": "Execute SQL queries on PostgreSQL",
      "category": "database",
      "docker_image": "mcp/postgres:latest",
      "default_env": {
        "PORT": "8080",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "mydb",
        "POSTGRES_USER": "{{ bw:postgres-creds:username }}",
        "POSTGRES_PASSWORD": "{{ bw:postgres-creds:password }}"
      },
      "required_secrets": ["POSTGRES_USER", "POSTGRES_PASSWORD"],
      "documentation_url": "https://github.com/example/mcp-postgres",
      "tags": ["postgresql", "database", "sql"]
    }
  ],
  "categories": [
    {
      "id": "development",
      "name": "Development",
      "description": "Development and version control tools"
    },
    {
      "id": "database",
      "name": "Database",
      "description": "Database management and query tools"
    }
  ]
}
```

## バリデーションルール

1. **必須フィールド**: すべての必須フィールドが存在すること
2. **一意のID**: サーバーIDとカテゴリIDはカタログ内で一意であること
3. **有効なカテゴリ**: サーバーの `category` は定義されたカテゴリIDを参照していること
4. **Dockerイメージ**: 有効なDockerイメージ名であること
5. **URL**: 有効なHTTP/HTTPS URLであること
6. **Bitwarden参照**: 形式 `{{ bw:item-id:field }}` に従うこと

## カタログのホスティング

### オプション 1: GitHub

GitHubリポジトリでカタログをホストする：

```
https://raw.githubusercontent.com/username/repo/main/catalog.json
```

### オプション 2: 静的ホスティング

任意の静的ファイルサーバーでホストする：
- AWS S3
- Google Cloud Storage
- Netlify
- Vercel
- 独自のWebサーバー

### オプション 3: CDN

パフォーマンス向上のためにCDNを使用する：
- Cloudflare
- AWS CloudFront
- Fastly

## ベストプラクティス

1. **最新の状態に保つ**: `last_updated` タイムスタンプを定期的に更新する
2. **セマンティックバージョニング**: Dockerイメージタグにはセマンティックバージョニングを使用する
3. **明確な説明**: 明確で簡潔な説明を書く
4. **有用なタグ**: 検索性を高めるために適切なタグを追加する
5. **ドキュメント**: 常にドキュメントURLを提供する
6. **イメージのテスト**: すべてのDockerイメージがパブリックにアクセス可能であることを確認する
7. **セキュリティ**: 実際のシークレットをカタログに決して含めないこと
8. **バリデーション**: 公開前にカタログJSONを検証する

## カタログのテスト

1. **JSONバリデーション**: 構文チェックのためにJSONバリデータを使用する
2. **スキーマバリデーション**: スキーマに対して検証する
3. **手動テスト**: コンソールにカタログを読み込み、インストールをテストする
4. **イメージ可用性**: すべてのDockerイメージがプル可能であることを確認する

## バリデーションスクリプト例

```bash
#!/bin/bash
# validate-catalog.sh

# JSON構文チェック
jq empty catalog.json || exit 1

# 必須フィールドチェック
jq -e '.version' catalog.json > /dev/null || exit 1
jq -e '.servers' catalog.json > /dev/null || exit 1

# サーバーID重複チェック
DUPLICATES=$(jq -r '.servers[].id' catalog.json | sort | uniq -d)
if [ -n "$DUPLICATES" ]; then
  echo "Duplicate server IDs found: $DUPLICATES"
  exit 1
fi

echo "Catalog validation passed!"
```

## カタログの更新

カタログを更新する場合：

1. `last_updated` タイムスタンプを更新
2. 変更されたサーバーのバージョン番号をインクリメント
3. すべての変更をローカルでテスト
4. ホスティング場所にコミットしてプッシュ
5. コンソールはキャッシュTTLに基づいて自動的に更新を取得します

## サポート

カタログスキーマに関する質問や問題について：
- このドキュメントを確認
- サンプルカタログを確認: `docs/sample-catalog.json`
- GitHubでIssueを作成

## カタログAPI

カタログを取得するためのAPIエンドポイントの仕様です。

### エンドポイント

`GET /api/catalog`

### パラメータ

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|---|---|---|---|---|
| `source` | string (enum) | いいえ | `docker` | カタログソースID。`docker` (Docker MCP Gateway) または `official` (Official MCP Registry) を指定可能。 |

### エラーレスポンス

エラー発生時は以下の構造化されたJSONが返却されます。

```json
{
  "detail": "エラーの詳細メッセージ",
  "error_code": "エラーコード",
  "retry_after_seconds": 60
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `detail` | string | 人間可読なエラーメッセージ |
| `error_code` | string (enum) | 機械可読なエラーコード |
| `retry_after_seconds` | integer | (省略可) 再試行が可能になるまでの秒数。レート制限時に設定されます。 |

#### エラーコード一覧

| コード | HTTPステータス | 説明 |
|---|---|---|
| `invalid_source` | 400 | 指定された `source` が無効です。 |
| `rate_limited` | 429 | 上流レジストリのレート制限に達しました。`retry_after_seconds` 後に再試行してください。 |
| `upstream_unavailable` | 503 | 上流レジストリに接続できないか、タイムアウトしました。 |
| `internal_error` | 500 | 内部エラーが発生しました。 |

### 使用例

#### リクエスト例

```bash
# Dockerカタログを取得 (デフォルト)
curl http://localhost:8000/api/catalog

# Official Registryカタログを取得
curl http://localhost:8000/api/catalog?source=official
```

#### エラーレスポンス例 (レート制限)

```json
{
  "detail": "Rate limit exceeded. Please try again in 60 seconds.",
  "error_code": "rate_limited",
  "retry_after_seconds": 60
}
```
