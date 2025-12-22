# Research & Design Decisions: mcp-registry-source-selector

---
**Purpose**: カタログソースセレクター機能のディスカバリ調査結果と設計判断の根拠を記録する。

**Usage**:
- 設計フェーズでの調査活動と結果をログ化
- `design.md` に含めるには詳細すぎるトレードオフを文書化
- 将来の監査や再利用のための参照と根拠を提供
---

## Summary
- **Feature**: `mcp-registry-source-selector`
- **Discovery Scope**: Extension（既存システムの拡張）
- **Key Findings**:
  1. 現在の `source` パラメータは任意 URL を受け付けており、セキュリティ上プリセットに制限する必要がある
  2. Official MCP Registry (`registry.modelcontextprotocol.io`) は JSON-RPC 2.0 / REST API を提供し、`servers` 配列を含むレスポンスを返す
  3. 既存の `CatalogService._convert_explore_server` が Official Registry 形式を部分的にサポート済み

## Research Log

### Official MCP Registry エンドポイント調査
- **Context**: Requirement 2 で「Official MCP Registry」からのデータ取得が必要
- **Sources Consulted**:
  - ModelContextProtocol.io 公式ドキュメント
  - GitHub modelcontextprotocol/registry リポジトリ
  - NordicAPIs の MCP Registry OpenAPI 解説記事
- **Findings**:
  - Official Registry API は `registry.modelcontextprotocol.io` でホストされている
  - エンドポイント例: `GET /v0/servers` で登録済みサーバー一覧を取得可能
  - レスポンス形式は `{ servers: [...] }` で、各サーバーは `server` オブジェクト内に `name`, `description`, `repository`, `packages` を持つ
  - 既存 `_convert_explore_server` は `item.server` 形式を処理するロジックを持っており、互換性が高い
- **Implications**:
  - バックエンドでは URL をハードコードせず `config.py` で管理
  - スキーマ変換は既存ロジックを流用可能だが、フィールド欠損時のフォールバックを強化

### Docker MCP Registry エンドポイント確認
- **Context**: 既存ソース（DockerMCPCatalog）の動作を維持する必要あり
- **Sources Consulted**:
  - `backend/app/config.py` の `catalog_default_url` 定義
  - `backend/app/services/catalog.py` の GitHub Contents API 処理
- **Findings**:
  - 現在のデフォルト URL: `https://api.github.com/repos/docker/mcp-registry/contents/servers`
  - GitHub Contents API 形式（ディレクトリ一覧 + 個別 `server.yaml` フェッチ）を処理
  - `GITHUB_TOKEN` によるレート制限回避が可能
- **Implications**:
  - DockerMCPCatalog は既存動作を維持（Requirement 6 対応）
  - ソース ID `docker` → 現在の `catalog_default_url` にマッピング

### フロントエンド UI パターン調査
- **Context**: テキスト入力からセレクタへの UI 変更
- **Sources Consulted**:
  - `frontend/app/catalog/page.tsx` の現在の実装
  - プロジェクトの Tailwind CSS スタイルガイド
- **Findings**:
  - 現在は `<input type="text">` でフリーフォーム URL を入力
  - `useState` でローカル管理し、変更時に `setCatalogSource` で反映
  - SWR の `cacheKey` に `catalogSource` が含まれている
- **Implications**:
  - `<select>` または RadioGroup に置き換え、プリセット定数を定義
  - バックエンドへは ID 文字列 (`docker`, `official`) を送信

### セキュリティ要件とバリデーション
- **Context**: Requirement 5 でプリセット限定とシークレット非露出が求められている
- **Sources Consulted**:
  - OWASP API Security Top 10
  - プロジェクトの `tech.md` / `structure.md`
- **Findings**:
  - 現在の API は任意 URL をそのままフェッチするため SSRF リスクあり
  - バックエンドでホワイトリスト検証を行い、未知の `source` は 400 で拒否すべき
  - GitHub Token などの認証情報はレスポンスやエラーメッセージに露出させない
- **Implications**:
  - `CatalogSourceId` Enum を定義し、Pydantic でバリデーション
  - 400 エラー時は詳細な内部情報を含めない

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| A: Extend Existing | `CatalogPage` と `CatalogService` を拡張 | 最小限の変更、既存キャッシュ利用可能 | URL 直接受付の後方互換性に注意 | **推奨** |
| B: New Components | `CatalogSourceSelector` と `CatalogSourceManager` を新設 | 責務が明確 | 機能規模に対してオーバーエンジニアリング | - |

## Design Decisions

### Decision: ソース ID ベースのマッピング方式
- **Context**: `source` パラメータの解釈を URL から ID に変更する必要がある
- **Alternatives Considered**:
  1. URL をそのまま受け付けるが、ホワイトリストで検証
  2. ID 文字列のみ受け付け、バックエンドで URL に変換
- **Selected Approach**: Option 2（ID 文字列方式）
- **Rationale**: セキュリティ上、許可された URL をバックエンドで厳密に管理できる。フロントエンドに URL を露出させない。
- **Trade-offs**: 新しいソースを追加する際はバックエンドの変更が必要だが、セキュリティ優先で許容可能
- **Follow-up**: 環境変数で Official Registry URL を上書き可能にするか検討

### Decision: Enum による source バリデーション
- **Context**: 不正な `source` 値の拒否方法
- **Alternatives Considered**:
  1. 文字列比較による if/else
  2. Python Enum + Pydantic バリデーション
- **Selected Approach**: Option 2（Enum）
- **Rationale**: 型安全性が高く、FastAPI の自動ドキュメント生成にも対応
- **Trade-offs**: Enum 定義の追加が必要だが、保守性向上
- **Follow-up**: なし

### Decision: フロントエンドでのプリセット定数管理
- **Context**: セレクタの選択肢をどこで定義するか
- **Alternatives Considered**:
  1. バックエンドの `/api/catalog/sources` エンドポイントから取得
  2. フロントエンドに定数として定義
- **Selected Approach**: Option 2（フロントエンド定数）
- **Rationale**: プリセットは固定であり、追加のAPI呼び出しは不要。シンプルさ優先。
- **Trade-offs**: ソース追加時はフロント/バック両方の変更が必要だが、頻度は低い
- **Follow-up**: 将来的に動的ソース追加が必要になれば Option 1 を検討

## Risks & Mitigations
- **Official Registry の可用性**: 一時的なダウンでユーザー体験が損なわれる → キャッシュ機構と Docker ソースへのフォールバック案内で対応
- **Official Registry のスキーマ変更**: 予告なしの形式変更でパース失敗 → エラーハンドリングと警告表示、ログ記録で早期検知
- **後方互換性**: 既存クライアントが URL を送る可能性 → Web Console は自己完結しているため影響軽微。必要に応じて移行期間中は URL も許容するフラグを検討

## References
- [ModelContextProtocol.io - Official Documentation](https://modelcontextprotocol.io/) — プロトコル仕様とレジストリ概要
- [GitHub docker/mcp-registry](https://github.com/docker/mcp-registry) — Docker MCP カタログソース
- [NordicAPIs - MCP Registry OpenAPI](https://nordicapis.com/) — OpenAPI 仕様解説
- gap-analysis.md — 本機能のギャップ分析
