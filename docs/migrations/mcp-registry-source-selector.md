# MCP Registry Source Selector 移行ガイド

## 概要

`mcp-registry-source-selector` 機能の導入に伴い、カタログソースの管理方法が変更されました。従来の「単一の Docker カタログ URL」から、「Docker」および「Official」のプリセット選択方式へ移行します。これに伴い、環境変数の構成と優先順位が変更されています。

本ドキュメントでは、新しい環境変数の仕様、既存設定からの移行手順、および非推奨化のタイムラインについて説明します。

## 環境変数の変更点

### 新しい環境変数

| 変数名 | 説明 | デフォルト値 | 必須 |
|---|---|---|---|
| `CATALOG_OFFICIAL_URL` | Official MCP Registry の URL | `https://registry.modelcontextprotocol.io/v0/servers` | いいえ |
| `CATALOG_DOCKER_URL` | Docker MCP Catalog の URL | `CATALOG_DEFAULT_URL` の値 | いいえ |

### 非推奨となる環境変数

| 変数名 | 現在の状態 | 代替手段 | 説明 |
|---|---|---|---|
| `CATALOG_DEFAULT_URL` | **非推奨 (Deprecated)** | `CATALOG_DOCKER_URL` | Docker カタログの URL 定義に使用されます。後方互換性のため当面維持されますが、将来的に削除される予定です。 |

## 移行ガイド

### 1. 新旧マッピング表

環境変数の優先順位と読み替えルールは以下の通りです。既存の `NEXT_PUBLIC_CATALOG_URL` はセキュリティ強化（クライアントからの任意 URL 送信禁止）のため無視されるようになりますが、バックエンド側の設定は最大限尊重されます。

| 新環境変数 | 旧環境変数 | 優先順位 | 読み替えルール |
|---|---|---|---|
| - | `NEXT_PUBLIC_CATALOG_URL` | - | **廃止 (Ignored)**。フロントエンドはプリセット ID (`docker`, `official`) のみを送信するため、この変数は無視されます。 |
| `CATALOG_OFFICIAL_URL` | (新規) | 1 | Official ソース選択時に使用されます。未設定時はデフォルト値が使用されます。 |
| `CATALOG_DOCKER_URL` | `CATALOG_DEFAULT_URL` | 2 | Docker ソース選択時に使用されます。`CATALOG_DOCKER_URL` が未設定の場合、`CATALOG_DEFAULT_URL` の値が使用されます（後方互換）。 |

### 2. 設定例と手順

#### ケース A: ローカル開発 (`.env.local` / `.env`)

開発環境では、`backend/.env` を更新して明示的に新しい変数を使用することを推奨します。

**変更前 (.env):**
```env
CATALOG_DEFAULT_URL=https://api.github.com/repos/docker/mcp-registry/contents/servers
```

**変更後 (推奨):**
```env
# Docker Catalog URL (旧 CATALOG_DEFAULT_URL)
CATALOG_DOCKER_URL=https://api.github.com/repos/docker/mcp-registry/contents/servers

# Official Registry URL (オプション、デフォルト値で十分な場合は省略可)
CATALOG_OFFICIAL_URL=https://registry.modelcontextprotocol.io/v0/servers
```

#### ケース B: Docker / クラウド環境 (`docker-compose.yml`)

`docker-compose.yml` またはデプロイメント設定で環境変数を指定している場合も同様に更新します。

**docker-compose.yml 例:**

```yaml
services:
  backend:
    environment:
      # 移行期間中は CATALOG_DEFAULT_URL も維持可能ですが、警告ログが出力される場合があります
      - CATALOG_DOCKER_URL=https://my-custom-mirror.example.com/docker/servers
      - CATALOG_OFFICIAL_URL=https://registry.modelcontextprotocol.io/v0/servers
```

### 3. 段階的移行手順

安全に移行するためのステップバイステップガイドです。

1.  **検証 (Verification)**:
    *   本機能をステージング環境にデプロイし、Catalog ページで "Docker" と "Official" の切り替えが機能することを確認します。
    *   既存の `CATALOG_DEFAULT_URL` 設定が残っている場合、"Docker" ソース選択時にその URL が使用されていることを確認します。

2.  **移行 (Migration)**:
    *   本番環境の環境変数を更新し、`CATALOG_DOCKER_URL` を設定します。
    *   `CATALOG_DEFAULT_URL` は削除するか、万が一のロールバック用に一時的に残します。
    *   `NEXT_PUBLIC_CATALOG_URL` が設定されている場合は削除します（不要になります）。

3.  **切替 (Switch)**:
    *   ユーザーに新しい「ソース選択機能」を周知します。
    *   デフォルトで "Docker" が選択されているため、既存ユーザーの体験は維持されます。

4.  **廃止 (Cleanup)**:
    *   非推奨終了日以降、`CATALOG_DEFAULT_URL` のサポートが完全に削除されます。それまでにすべての環境で設定を更新してください。

## 非推奨タイムライン

| フェーズ | 時期 | アクション |
|---|---|---|
| **Phase 1 (現在)** | 本機能リリース時 | `CATALOG_DEFAULT_URL` を非推奨としてマーク。ログに警告が出力される可能性がありますが、機能は維持されます。 |
| **Phase 2** | 次期メジャーリリース | ドキュメントから `CATALOG_DEFAULT_URL` の記載を削除。 |
| **Phase 3** | 2026年3月予定 | `CATALOG_DEFAULT_URL` のサポートを完全終了。`CATALOG_DOCKER_URL` が必須となります。 |

## 方針説明

私たちは既存の運用環境を尊重し、急激な変更による中断を避ける方針をとっています。そのため、`CATALOG_DEFAULT_URL` は当面の間サポートされ続け、意図した通りに Docker カタログのソースとして機能します。しかし、より明確な構成と将来の拡張性（複数のソース管理）のために、新しい `CATALOG_DOCKER_URL` および `CATALOG_OFFICIAL_URL` への移行を強く推奨します。
