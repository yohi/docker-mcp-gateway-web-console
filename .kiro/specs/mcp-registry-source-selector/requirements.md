# Requirements Document

## Project Description (Input)
既存の「Docker MCP Gateway Web Console」において、サーバーカタログの取得元として現在の `DockerMCPCatalog` に加え、`Official MCP Registry` を選択・利用できるように拡張する。

ユーザーがカタログソースのURLを手入力する手間を省くため、フロントエンドの入力フォームをセレクタ形式に変更し、プリセットされたソース（Docker / Official）を簡単に切り替えられるようにする。データ取得は既存のバックエンド処理を拡張し、レート制限回避とデータ変換をサーバーサイドで行う。

### 技術スタック

| 項目 | 内容 |
| --- | --- |
| 言語 | Python (FastAPI), TypeScript (Next.js) |
| フレームワーク | FastAPI, Next.js (App Router), Tailwind CSS |
| 開発形態 | 既存システムへの追加・改修 (Brownfield) |

### 開発・テスト環境の制約
- **DevContainer要件**: 既存の `.devcontainer` 環境を開発・テスト環境として使用すること
- **テスト実行ポリシー**: すべての自動テストは DevContainer内でのみ実行すること

### 主要機能
1. **フロントエンド改修**: カタログソース選択UIをセレクタ形式に変更
2. **バックエンド改修**: Official MCP Registry形式のJSONパース対応
3. **API拡張**: `GET /api/catalog` のsourceパラメータ対応

## Introduction
本仕様は、Docker MCP Gateway Web Console のサーバーカタログ取得元として既存の `DockerMCPCatalog` に加え `Official MCP Registry` を選択可能にし、ユーザーがプリセットされたソースをセレクタで簡単に切り替えられることを目的とする。あわせてバックエンドは複数ソースから取得したカタログを同一のレスポンススキーマとして提供し、UI は同一の操作体験で一覧表示・再取得を行えることを保証する。

## Requirements

### Requirement 1: カタログソース選択 UI（プリセット）
**Objective:** As a ユーザー, I want カタログ取得元をプリセットから選択できる, so that URL を手入力せずに目的のカタログに切り替えられる

#### Acceptance Criteria
1. The Web Console UI shall provide a catalog source selector that offers `DockerMCPCatalog` and `Official MCP Registry`
2. When ユーザーがカタログソースを変更する, the Web Console UI shall refresh the catalog list using the newly selected source
3. When カタログ画面を初回表示する, the Web Console UI shall set the selected source to `DockerMCPCatalog`
4. While カタログ取得リクエストが進行中である, the Web Console UI shall display a loading state for the catalog list
5. If カタログ取得が失敗した, the Web Console UI shall display an error state and provide a retry action

### Requirement 2: `GET /api/catalog` の `source` パラメータ
**Objective:** As a フロントエンド, I want `source` で取得元を指定できる, so that 選択されたカタログソースに応じたデータを取得できる

#### Acceptance Criteria
1. The Backend API shall accept `source` as a query parameter on `GET /api/catalog`
2. When `source` is omitted, the Backend API shall treat the request as `source=DockerMCPCatalog`
3. When `source` is `DockerMCPCatalog`, the Backend API shall return the catalog using the existing Docker catalog behavior
4. When `source` is `Official MCP Registry`, the Backend API shall return the catalog using the Official MCP Registry as the upstream source
5. If `source` is not a supported value, the Backend API shall return an HTTP 400 response

### Requirement 3: カタログデータの正規化（ソース差異吸収）
**Objective:** As a ユーザー, I want どの取得元でも同じ形式でカタログを閲覧できる, so that 取得元の違いを意識せずにサーバーを探せる

#### Acceptance Criteria
1. The Catalog Service shall return catalog data in a single consistent response schema for all supported sources
2. When upstream data uses a different schema, the Catalog Service shall map it into the Web Console catalog schema
3. If an upstream item cannot be mapped into the required schema, the Catalog Service shall exclude the item from the response
4. If upstream data contains unknown fields, the Catalog Service shall ignore the unknown fields
5. The Catalog Service shall ensure each returned catalog entry includes a stable identifier and display name required by the Web Console

### Requirement 4: 上流障害・レート制限時の振る舞い
**Objective:** As a ユーザー, I want 取得失敗時に理由と復旧手段が分かる, so that 再試行や別ソースへの切り替えで作業を継続できる

#### Acceptance Criteria
1. If upstream responds with a rate limit condition, the Catalog Service shall return an error response that indicates rate limiting
2. If upstream is unavailable or times out, the Catalog Service shall return an error response that indicates upstream unavailability
3. When the Web Console UI receives a rate limiting error, the Web Console UI shall inform the user that retry is required
4. When the Web Console UI receives an upstream unavailability error, the Web Console UI shall inform the user and provide a retry action
5. While an error is shown, the Web Console UI shall preserve the user selected catalog source

### Requirement 5: セキュリティ（プリセット限定と秘匿情報の非露出）
**Objective:** As a 管理者, I want カタログ取得先をプリセットに限定できる, so that 任意 URL 取得や秘匿情報露出のリスクを抑えられる

#### Acceptance Criteria
1. The Backend API shall restrict catalog fetching to the supported preset sources
2. If a client provides an unsupported or malformed `source`, the Backend API shall not initiate any outbound request to an upstream registry
3. The Web Console UI shall not provide a free-form input for arbitrary catalog source URLs in the catalog source selection flow
4. The Backend API shall not expose any upstream authentication secrets to the client in responses or error messages
5. Where upstream authentication is configured, the Backend API shall use it without requiring the client to supply secrets per request

### Requirement 6: 互換性（既存動作の維持）
**Objective:** As a 既存ユーザー, I want 何もしなくても従来通りカタログを利用できる, so that 既存の利用体験が壊れない

#### Acceptance Criteria
1. When existing clients call `GET /api/catalog` without specifying `source`, the Backend API shall return a response compatible with the pre-feature schema
2. When ユーザーがカタログソースを変更しない, the Web Console UI shall behave as if `DockerMCPCatalog` is selected
3. The system shall continue to support the existing Docker catalog source without requiring additional configuration
4. If `Official MCP Registry` is temporarily unavailable, the system shall still allow use of `DockerMCPCatalog`
5. When ユーザーがカタログソースを切り替える, the Web Console UI shall allow switching sources without requiring a page reload
