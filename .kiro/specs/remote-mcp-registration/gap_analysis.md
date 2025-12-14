# Gap Analysis: リモートMCPサーバー登録 (remote-mcp-registration)

## 1. 現状調査 (Current State Investigation)

### 既存アセットと構造
- **CatalogService (`backend/app/services/catalog.py`)**:
  - MCP サーバー定義の取得・キャッシュ・検索を担当。
  - **制約**: `_filter_items_missing_image` により、`docker_image` が未定義のアイテムを強制的に除外している。リモート MCP サーバー (SaaS 等) は Docker イメージを持たないため、現在の実装ではカタログから認識されない。
  - **データモデル**: `CatalogItem` は `oauth_authorize_url` などのフィールドを既に持っており、モデルレベルの準備はある程度できている。

- **OAuthService (`backend/app/services/oauth.py`)**:
  - PKCE (S256) 対応の認可フロー、トークン暗号化 (Fernet)、状態管理 (`state`) を実装済み。
  - **制約**: `state` の管理がメモリ内辞書 (`_state_store_mem`) で行われている。バックエンド再起動で検証不能になるリスクがある（要件ではセッションストア推奨）。
  - **適合性**: リフレッシュトークン、監査ログ、スコープ検証などは要件を概ね満たしている。

- **ContainerService (`backend/app/services/containers.py`)**:
  - Docker コンテナのライフサイクル (作成・起動・停止) を厳格に管理する。
  - **制約**: `docker.DockerClient` に強く依存しており、"コンテナ以外" (リモート接続など) の実行単位を扱う概念が存在しない。「登録済みサーバー」＝「Docker コンテナ」という前提がある。

- **GatewayService (`backend/app/services/gateways.py`)**:
  - 外部/E2B ゲートウェイの許可リストとヘルスチェック用。
  - **制約**: MCP プロトコルレベルの統合や中継機能を持たない。単なる URL 管理と疎通確認に留まっている。

- **Frontend**:
  - コンテナ一覧、カタログ一覧が表示可能だが、Docker イメージ前提の UI となっている。OAuth 認可開始の UI フローは GitHub トークン用などに一部存在するが、汎用的な MCP サーバー向けフローとしては整備が必要。

### 統合ポイント
- **Runtime**: 現在の Gateway ランタイムは、ローカル Docker コンテナの Stdio と通信することを前提としている可能性が高い。リモート MCP (SSE) とのブリッジ機能が欠落している。
- **Persistence**: `state.db` (SQLite) はコンテナ設定、ゲートウェイ設定、資格情報などを保存している。リモートサーバー設定を保存するテーブル/モデルが必要。

## 2. 要件適合性分析 (Requirements Feasibility Analysis)

### 不足機能 (Gaps)
1.  **カタログでの非 Docker アイテムサポート**: `docker_image` 必須制約の撤廃または緩和が必要。
2.  **リモートサーバー管理**: Docker コンテナではない「リモートサーバー」を登録・永続化する仕組み。`GatewayRecord` と `ContainerRecord` の中間のような概念が必要。
3.  **プロトコル変換ブリッジ**: ローカルの Stdio 要求（Gateway クライアントから）を、リモートの SSE/HTTP エンドポイントへ変換・中継するランタイムロジック (SSE Client)。
4.  **OAuth State の永続化 (推奨)**: メモリ依存からの脱却。
5.  **UI 対応**: リモートサーバー用の「接続」「認証」アクションの実装。

### 複雑性シグナル
- **プロトコル変換**: Stdio <-> SSE の変換は双方向かつ非同期であり、技術的な複雑性が高い。これを「Gateway Runtime」内で行うか、専用の「ブリッジコンテナ」を立てるかでアーキテクチャが変わる。
- **抽象化の欠如**: 現在の「サーバー管理」は完全に Docker に依存しているため、これを「Docker も含めた汎用サーバー」へ抽象化する変更は影響範囲が大きい。

## 3. 実装アプローチ案 (Implementation Options)

### Option A: 既存サービス拡張と仮想コンテナ化 (Extend & Virtualize)
`ContainerService` を抽象化し、Docker コンテナだけでなく「仮想コンテナ (Remote Server)」も扱えるようにする。

- **アーキテクチャ**:
  - `ServerService` (仮) のような抽象層を導入、または `ContainerService` に `RunMode` (Docker/Remote) を追加。
  - リモートサーバーも「実行中」のサーバーとしてリストアップされる。
  - 実際の通信は `ConnectionManager` が Docker SDK または SSE Client を使い分ける。
- **メリット**: フロントエンドの変更が最小限（既存のコンテナ一覧 UI を流用可能）。「サーバー」という概念が統一される。
- **デメリット**: `ContainerService` が肥大化し、責務が曖昧になる（Docker 操作と HTTP 通信が混在）。

### Option B: リモート専用サービスの追加 (New Remote Service)
`RemoteMcpService` を新設し、Docker とは完全に分離して管理する。

- **アーキテクチャ**:
  - `backend/app/services/remote_mcp.py` を作成。DB にも `remote_servers` テーブルを追加。
  - 既存の `GatewayService` (External Gateway) と近いが、こちらは MCP プロトコルレベルの統合を行う。
  - UI 上も「Local Containers」と「Remote Servers」でタブを分けるなど明確に分離。
- **メリット**: 責務が明確。既存の安定した Docker 管理ロジックを汚染しない。
- **デメリット**: UI/API が分断され、ユーザーにとっては「MCP サーバーを使いたい」だけなのに二重管理になる可能性がある。

### Option C: 統合 Runtime への進化 (Hybrid / Evolution)
「Gateway Runtime」を Docker 制御から切り離し、接続先 (Location) を抽象化した `McpRuntimeService` を構築する。

- **アーキテクチャ**:
  - `ContainerService` はあくまで「Docker プロセスの管理」に専念。
  - 新設する `McpInstanceService` が「MCP サーバーとしての実体」を管理し、バックエンドとして `ContainerService` (ローカル) や `RemoteClient` (リモート) を使用する。
  - カタログも `type: docker` | `type: remote` を持つように拡張。
- **メリット**: 最もアーキテクチャとして綺麗で、将来の拡張（K8s 対応や WASM 対応など）に強い。
- **デメリット**: リファクタリング規模が大きく (XL)、現在のフェーズでは過剰エンジニアリングのリスク。

## 4. 推奨と結論 (Recommendations)

### リスクと複雑性
- **Effort**: **L (1-2 weeks)** - プロトコル変換の実装と、既存の Docker 前提ロジックの解消に工数がかかる。
- **Risk**: **Medium** - SSE クライアントの実装自体はライブラリ利用で可能だが、既存システムへの統合における後方互換性維持に注意が必要。

### 推奨アプローチ
**Option B (New Remote Service) をベースにしつつ、UI/API 層で統合を見せるアプローチ** を推奨する。

既存の `ContainerService` は Docker の複雑さを隠蔽するために高度に特化しているため、無理に拡張するとバグの温床となる。
1. `RemoteMcpService` を新設し、定義の登録・永続化・Status管理・OAuth連携を担当させる。
2. `CatalogService` の `docker_image` 必須チェックを「`docker_image` OR `remote_endpoint` が存在すること」に緩和する。
3. `GatewayRuntime` (新規詳細設計が必要) として、SSE クライアント機能を実装し、登録された Remote Server への透過的なアクセスを提供する。

### Design Phase への申し送り事項
- **Research Needed**: Python の MCP SDK (`mcp` パッケージ) における SSE Client の実装詳細と、それを FastAPI 上でどう扱うか (ASGI/Websocket との兼ね合い) の調査。
- **Decision**: OAuth の `state` を `StateStore` (SQLite) に永続化するかどうか。要件に従い推奨されるが、スキーマ変更が必要。
- **Decision**: リモートサーバーの「接続テスト」の定義（単なる HTTP Ping か、MCP Ping か）。

