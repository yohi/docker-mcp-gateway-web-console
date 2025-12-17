# Research & Design Decisions: リモートMCPサーバー登録

## Summary
- **Feature**: `remote-mcp-registration`
- **Discovery Scope**: Complex Integration（新規サービス追加 + 既存サービス拡張 + プロトコル変換）
- **Key Findings**:
  1. MCP Python SDK (`mcp` パッケージ) は SSE/HTTP トランスポートをネイティブサポートしており、`sse_client` ユーティリティを用いてリモート MCP サーバーへ接続可能
  2. 既存の OAuth 実装 (OAuthService) は PKCE/state を完全実装しているが、state のメモリ管理をセッションストア永続化へ移行する必要がある
  3. CatalogService の `docker_image` 必須フィルタが、リモート MCP サーバー（SaaS）の認識を妨げている

## Research Log

### MCP Python SDK SSE Client Transport
- **Context**: リモート MCP サーバー (SSE/HTTP) との通信方式を調査
- **Sources Consulted**:
  - https://github.com/modelcontextprotocol/python-sdk (公式 Python SDK)
  - SDK README および examples/servers/sse-polling-demo
- **Findings**:
  - `mcp.client.sse` モジュールで `sse_client()` コンテキストマネージャを提供
  - `ClientSession` を用いて `initialize()`, `list_tools()`, `call_tool()` 等を呼び出し可能
  - トランスポートは Stdio/SSE/WebSocket の 3 種をサポート
  - SSE クライアントは `httpx-sse` を内部で使用
- **Implications**:
  - バックエンドへ `mcp` パッケージを追加依存として導入
  - `RemoteMcpClient` ラッパーを作成し、既存の `GatewayService` パターンを踏襲
  - 接続テスト (Requirement 6.5) は `session.initialize()` + `session.list_tools()` のレスポンスを確認する形で実現可能

### 既存 OAuth 実装の互換性
- **Context**: Requirement 3, 4 の OAuth 2.0 + PKCE 要件を既存実装で満たせるか検証
- **Sources Consulted**:
  - `backend/app/services/oauth.py` (現行実装)
  - Requirement 3.2–3.7 (PKCE 詳細)
- **Findings**:
  - `OAuthService.start_auth()` は `code_challenge`, `code_challenge_method` (S256) をサポート済み
  - `_state_store_mem` (Dict) によるメモリ管理 → バックエンド再起動で state が失われる
  - `TokenCipher` で Fernet 暗号化済み、要件 5.1–5.3 を満たす
  - `_record_audit()` で監査ログ記録済み (Requirement 9.3)
- **Implications**:
  - state を `StateStore` (SQLite) へ永続化するスキーマ追加が必要
  - `OAuthService` に `server_id` を紐付けるロジックを追加し、リモートサーバーごとの認証状態管理を実現

### CatalogItem モデルとフィルタリング
- **Context**: リモート MCP サーバーがカタログから除外される問題
- **Sources Consulted**:
  - `backend/app/services/catalog.py` (`_filter_items_missing_image`)
  - `backend/app/models/catalog.py` (`CatalogItem`)
- **Findings**:
  - `CatalogItem` は `oauth_authorize_url`, `oauth_token_url` フィールドを既に持つ
  - `_filter_items_missing_image()` が `docker_image` 空のアイテムを強制除外
  - リモートサーバーは `remote_endpoint` (SSE URL) を持つが、`docker_image` は持たない
- **Implications**:
  - `CatalogItem` に `server_type: Literal["docker", "remote"]` と `remote_endpoint: str | None` を追加
  - フィルタ条件を「`docker_image` または `remote_endpoint` が存在」に緩和

### StateStore 拡張可能性
- **Context**: リモートサーバー設定と OAuth state の永続化先
- **Sources Consulted**:
  - `backend/app/services/state_store.py`
  - `backend/app/models/state.py`
- **Findings**:
  - SQLite ベースで `credentials`, `sessions`, `gateway_allowlist` 等を管理
  - スキーマ追加は `init_schema()` 内の `CREATE TABLE IF NOT EXISTS` で容易
  - `_migrate_columns()` パターンで既存 DB への非破壊的カラム追加が可能
- **Implications**:
  - `remote_servers` テーブルを新設（`server_id`, `catalog_item_id`, `status`, `credential_key`, `created_at`）
  - `oauth_states` テーブルを新設（`state`, `server_id`, `code_challenge`, `expires_at`, `created_at`）

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| A: ContainerService 拡張 | Docker/Remote を抽象化 | UI 変更最小限 | 責務が曖昧化、Docker ロジック汚染 | 不採用 |
| B: RemoteMcpService 新設 | Docker から完全分離 | 責務明確、既存安定 | UI/API 分断 | **推奨** |
| C: McpRuntimeService 抽象層 | 統一された MCP 実体管理 | 将来拡張性 | 過剰エンジニアリング | 将来検討 |

## Design Decisions

### Decision: リモートサーバー管理を新規サービスとして分離
- **Context**: リモート MCP サーバーのライフサイクル管理方式の選定
- **Alternatives Considered**:
  1. ContainerService を拡張し、RunMode (Docker/Remote) を追加
  2. RemoteMcpService を新設し、Docker とは独立して管理
- **Selected Approach**: Option B — `RemoteMcpService` を新設
- **Rationale**: ContainerService は Docker SDK に強く依存しており、HTTP/SSE 通信ロジックを混在させると保守性が低下する。新規サービスによる責務分離がステアリング原則（サービス層集中）と合致。
- **Trade-offs**: UI/API が Docker コンテナとリモートサーバーで分かれるが、バックエンドの安定性を優先。
- **Follow-up**: 将来的には統一 UI への移行を検討

### Decision: OAuth state の永続化
- **Context**: Requirement 3.3, 4.1 で state の TTL 管理と単一使用が必須
- **Alternatives Considered**:
  1. メモリ内管理のまま（現状）
  2. Redis/Memcached へ移行
  3. SQLite (StateStore) へ追加
- **Selected Approach**: SQLite (StateStore) への `oauth_states` テーブル追加
- **Rationale**: 既存インフラ (SQLite) を活用し、追加依存を回避。TTL は `expires_at` カラムで管理し、GC で期限切れを削除。
- **Trade-offs**: 高頻度アクセス時のパフォーマンス懸念があるが、OAuth フローは低頻度のため許容範囲内。
- **Follow-up**: state 検証後の即時削除ロジックを実装

### Decision: プロトコル変換アプローチ
- **Context**: Requirement 6.2 の Stdio ↔ SSE 変換
- **Alternatives Considered**:
  1. バックエンド内で直接 SSE クライアントを呼び出し
  2. 専用ブリッジコンテナを起動
  3. Gateway コンテナ内に SSE モジュールを組み込み
- **Selected Approach**: バックエンド内で `mcp.client.sse` を使用して直接接続
- **Rationale**: 追加コンテナの複雑性を回避。MCP Python SDK が SSE をネイティブサポートしており、FastAPI 非同期コンテキスト内で動作可能。
- **Trade-offs**: バックエンドプロセスの負荷増加リスク。接続プールと適切なタイムアウト設定で対応。
- **Follow-up**: 高負荷時のスケーリング戦略を別途設計

## Risks & Mitigations
- **SSE 接続の長期化によるリソース枯渇** — 接続タイムアウト (30s) とアイドル検出で自動切断
- **OAuth state の TTL 超過による認証失敗** — GC ジョブで期限切れ state を定期削除、UI でエラー時の再認証ガイダンス
- **カタログ互換性破壊** — `server_type` フィールドはオプショナルとし、未指定時は `docker` をデフォルト

## References
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — 公式 SDK、SSE クライアント実装
- [RFC 7636 (PKCE)](https://tools.ietf.org/html/rfc7636) — OAuth 2.0 PKCE 仕様
- [Fernet (cryptography)](https://cryptography.io/en/latest/fernet/) — トークン暗号化方式
