[English](ARCHITECTURE.md)

# アーキテクチャドキュメント

このドキュメントでは、Docker MCP Gateway Consoleのアーキテクチャについて詳細に説明します。

## システム概要

Docker MCP Gateway Consoleは、Bitwarden統合を通じた安全なシークレット管理を備えた、DockerベースのMCPサーバーを管理するために設計された3層Webアプリケーションです。

## ハイレベルアーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                         Browser                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │           Next.js Frontend (React)                  │    │
│  │  • Authentication UI                                │    │
│  │  • Catalog Browser                                  │    │
│  │  • Container Dashboard                              │    │
│  │  • Config Editor                                    │    │
│  │  • MCP Inspector                                    │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ HTTPS / WebSocket
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Backend (Python)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Auth Service │  │Catalog Service│  │Container Svc │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │Config Service│  │Inspector Svc  │  │Secret Manager│     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                │                        │
                │                        │
                ▼                        ▼
┌──────────────────────┐    ┌──────────────────────┐
│   Docker Engine      │    │  Bitwarden Vault     │
│  • Container CRUD    │    │  • Secret Storage    │
│  • Log Streaming     │    │  • API/CLI Access    │
└──────────────────────┘    └──────────────────────┘
```

## コンポーネントアーキテクチャ

### フロントエンド層

#### 技術スタック
- **フレームワーク**: Next.js 14 with App Router
- **UIライブラリ**: React 18
- **言語**: TypeScript
- **スタイリング**: Tailwind CSS
- **状態管理**: React Context API + SWR
- **HTTPクライアント**: Fetch API
- **WebSocket**: Native WebSocket API

#### 主要コンポーネント

1. **認証モジュール** (`/app/auth`)
   - Bitwarden統合ログインフォーム
   - セッション管理
   - 保護されたルートのラッパー

2. **カタログブラウザ** (`/app/catalog`)
   - サーバー一覧と検索
   - カテゴリフィルタリング
   - インストールワークフロー

3. **コンテナダッシュボード** (`/app/dashboard`, `/app/containers`)
   - ステータス付きコンテナリスト
   - ライフサイクル制御（起動/停止/再起動/削除）
   - リアルタイムログビューア
   - コンテナ設定

4. **設定エディタ** (`/app/config`)
   - ゲートウェイ設定フォーム
   - Bitwarden参照入力
   - リアルタイムバリデーション

5. **MCPインスペクター** (`/app/inspector`)
   - ツール一覧ビューア
   - リソース一覧ビューア
   - プロンプト一覧ビューア

#### データフロー

```
User Action → Component → API Call → Backend
                ↓
         State Update (SWR/Context)
                ↓
            UI Re-render
```

### バックエンド層

#### 技術スタック
- **フレームワーク**: FastAPI
- **言語**: Python 3.11+
- **バリデーション**: Pydantic
- **Docker統合**: Docker SDK for Python
- **Bitwarden統合**: Bitwarden CLI
- **非同期ランタイム**: asyncio

#### サービスアーキテクチャ

```
┌─────────────────────────────────────────────────┐
│              API Layer (FastAPI)                 │
│  • Route handlers                                │
│  • Request validation                            │
│  • Response serialization                        │
│  • Error handling                                │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│              Service Layer                       │
│  ┌──────────────────────────────────────────┐  │
│  │ Auth Service                              │  │
│  │  • Bitwarden authentication              │  │
│  │  • Session management                    │  │
│  │  • Token validation                      │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ Secret Manager                            │  │
│  │  • Reference parsing                     │  │
│  │  • Bitwarden CLI interaction             │  │
│  │  • In-memory caching                     │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ Container Service                         │  │
│  │  • Docker API interaction                │  │
│  │  • Container lifecycle                   │  │
│  │  • Log streaming                         │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ Catalog Service                           │  │
│  │  • Catalog fetching                      │  │
│  │  • Search and filtering                  │  │
│  │  • Caching                               │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ Config Service                            │  │
│  │  • Configuration CRUD                    │  │
│  │  • Validation                            │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ Inspector Service                         │  │
│  │  • MCP protocol communication            │  │
│  │  • Capability discovery                  │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│           External Integrations                  │
│  • Docker Engine                                 │
│  • Bitwarden CLI                                 │
│  • MCP Servers                                   │
└─────────────────────────────────────────────────┘
```

## データモデル

### コアエンティティ

#### Session (セッション)
```python
class Session:
    session_id: str          # UUID v4
    user_email: str          # Bitwarden email
    bw_session_key: str      # Bitwarden CLI session
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
```

#### Container Configuration (コンテナ設定)
```python
class ContainerConfig:
    name: str
    image: str
    env: Dict[str, str]      # Bitwarden参照を含む可能性あり
    ports: Dict[str, int]
    volumes: Dict[str, str]
    labels: Dict[str, str]
```

#### Catalog Item (カタログアイテム)
```python
class CatalogItem:
    id: str
    name: str
    description: str
    category: str
    docker_image: str
    default_env: Dict[str, str]
    required_secrets: List[str]
    documentation_url: str
    tags: List[str]
```

## セキュリティアーキテクチャ

### 認証フロー

```
1. User enters credentials
   ↓
2. Frontend sends to /api/auth/login
   ↓
3. Backend authenticates with Bitwarden CLI
   ↓
4. Session created with UUID
   ↓
5. Session ID returned to frontend
   ↓
6. Frontend stores in memory (Context)
   ↓
7. All subsequent requests include session ID
```

### シークレット管理フロー

```
1. User enters Bitwarden reference: {{ bw:item-id:field }}
   ↓
2. Reference stored in configuration (not resolved)
   ↓
3. On container start:
   a. Parse all Bitwarden references
   b. Check in-memory cache
   c. If not cached, fetch from Bitwarden
   d. Cache in memory (session-scoped)
   e. Inject into container environment
   ↓
4. Container starts with resolved secrets
   ↓
5. On session end: Clear all cached secrets
```

### セキュリティ原則

1. **ディスク永続化なし**: シークレットは決してディスクに書き込まれない
2. **メモリのみの保存**: シークレットはセッション中のみメモリに保持される
3. **セッション分離**: 各セッションは分離されたキャッシュを持つ
4. **自動クリーンアップ**: ログアウト/タイムアウト時にシークレットを消去
5. **最小限の露出**: シークレットはターゲットコンテナにのみ露出される

## 通信パターン

### REST API

ほとんどの操作に対する標準的なリクエスト/レスポンス:

```
GET /api/containers
→ コンテナリストを返す

POST /api/containers
→ 新規コンテナを作成

PUT /api/config/gateway
→ ゲートウェイ設定を更新
```

### WebSocket

リアルタイムログストリーミング:

```
WebSocket /api/containers/{id}/logs
→ コンテナログをリアルタイムでストリーミング
→ 双方向通信
→ 切断時の自動再接続
```

### イベントフロー

```
Frontend Event → API Request → Service Logic → External System
                                      ↓
Frontend Update ← API Response ← Service Response
```

## キャッシュ戦略

### カタログキャッシュ

- **場所**: バックエンドメモリ
- **TTL**: 1時間（設定可能）
- **無効化**: 手動更新またはTTL期限切れ
- **目的**: 外部HTTPリクエストの削減

### シークレットキャッシュ

- **場所**: バックエンドメモリ（セッションごと）
- **TTL**: セッション寿命
- **無効化**: セッション終了
- **目的**: Bitwarden API呼び出しの削減

### フロントエンドキャッシュ (SWR)

- **場所**: ブラウザメモリ
- **TTL**: エンドポイントごとに設定可能
- **再検証**: フォーカス時、再接続時
- **目的**: UI応答性の向上

## デプロイアーキテクチャ

### 開発環境

```
┌─────────────────────────────────────┐
│      Docker Compose                  │
│  ┌──────────┐  ┌──────────┐        │
│  │ Frontend │  │ Backend  │        │
│  │  :3000   │  │  :8000   │        │
│  └──────────┘  └──────────┘        │
└─────────────────────────────────────┘
         │              │
         └──────┬───────┘
                │
         Host Docker Engine
```

### 本番環境

```
┌─────────────────────────────────────────────┐
│              Nginx (Reverse Proxy)           │
│         :80 (HTTP) → :443 (HTTPS)           │
└─────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
┌──────────────┐    ┌──────────────┐
│   Frontend   │    │   Backend    │
│   Container  │    │   Container  │
│    :3000     │    │    :8000     │
└──────────────┘    └──────────────┘
                           │
                           ▼
                  ┌──────────────┐
                  │Docker Engine │
                  └──────────────┘
```

## スケーラビリティの考慮事項

### 現在の制限

- シングルサーバーデプロイメント
- メモリ内セッションストレージ
- 水平スケーリングなし

### 将来の改善点

1. **セッションストレージ**: 分散セッションのためにRedisへ移行
2. **ロードバランシング**: 複数のバックエンドインスタンスのサポート
3. **データベース**: 設定の永続ストレージを追加
4. **メッセージキュー**: 長時間実行操作のためのキューを追加
5. **キャッシュレイヤー**: 分散キャッシュ (Redis/Memcached)

## パフォーマンス最適化

### フロントエンド

1. **コード分割**: Next.jsの自動コード分割
2. **画像最適化**: Next.js Imageコンポーネント
3. **遅延読み込み**: 重いコンポーネントの動的インポート
4. **キャッシング**: データフェッチとキャッシングのためのSWR

### バックエンド

1. **非同期操作**: FastAPIの非同期エンドポイント
2. **コネクションプーリング**: Docker SDKの接続再利用
3. **キャッシング**: 頻繁にアクセスされるデータのメモリ内キャッシング
4. **ストリーミング**: ログストリーミングのためのWebSocket

## 監視と可観測性

### ロギング

- **フロントエンド**: ブラウザコンソール（開発時）
- **バックエンド**: レベル付き構造化ロギング
- **コンテナ**: UI経由でアクセス可能なDockerログ

### ヘルスチェック

- **フロントエンド**: HTTPエンドポイントチェック
- **バックエンド**: `/health` エンドポイント
- **コンテナ**: Dockerヘルスチェック

### メトリクス（将来）

- リクエストレイテンシ
- エラー率
- コンテナリソース使用率
- キャッシュヒット率

## エラー処理

### フロントエンド

```
Try/Catch → Error Boundary → Toast Notification
                ↓
         Log to Console (dev)
```

### バックエンド

```
Exception → Exception Handler → HTTP Error Response
                ↓
         Log with Context
```

## テスト戦略

### 単体テスト

- **フロントエンド**: Jest + React Testing Library
- **バックエンド**: pytest

### 統合テスト

- **バックエンド**: Dockerテストコンテナを使用したpytest
- **フロントエンド**: コンポーネント統合テスト

### E2Eテスト

- **ツール**: Playwright
- **カバレッジ**: 重要なユーザーフロー

## 技術選定

### なぜNext.jsか？

- SEO向上のためのサーバーサイドレンダリング
- モダンなルーティングのためのApp Router
- 組み込みの最適化
- 優れた開発者体験

### なぜFastAPIか？

- 高パフォーマンス
- 自動APIドキュメント
- Pydanticによる型安全性
- 非同期サポート

### なぜBitwardenか？

- 業界標準のセキュリティ
- 自動化のためのCLIの提供
- セルフホスティングオプション
- 無料枠の利用可能

### なぜDockerか？

- MCPサーバーの分離
- 容易なデプロイ
- リソース管理
- 広い普及

## 将来のアーキテクチャ

### 計画されている改善

1. **マイクロサービス**: バックエンドをより小さなサービスに分割
2. **イベント駆動**: 非同期操作のためのメッセージキューの追加
3. **マルチテナンシー**: 複数ユーザー/組織のサポート
4. **Kubernetes**: Dockerに加えてK8sのサポート
5. **GraphQL**: より柔軟なAPIのためにGraphQLを検討

## 参考文献

- [Next.js Documentation](https://nextjs.org/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker SDK for Python](https://docker-py.readthedocs.io/)
- [Bitwarden CLI](https://bitwarden.com/help/cli/)
- [MCP Protocol](https://modelcontextprotocol.io/)
