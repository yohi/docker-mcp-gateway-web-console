# 設計書

## 概要

Docker MCP Gateway Web Consoleは、3層アーキテクチャ（フロントエンド、バックエンドAPI、Docker/Bitwarden統合層）で構成されるWebアプリケーションです。本システムは、Bitwardenを認証・機密情報管理の中核とし、Dockerコンテナとして実行されるMCPサーバー群を統合管理します。

主要な設計目標：
- **セキュリティ第一**: 機密情報をディスクに書き込まず、メモリ上でのみ処理
- **使いやすさ**: Catalogからの3クリック導入を実現
- **拡張性**: 新しいMCPサーバーやCatalogソースの追加が容易

## アーキテクチャ

### システム構成図

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (Client)                      │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │         Next.js Frontend (React)                 │   │
│  │  - Authentication UI                             │   │
│  │  - Catalog Browser                               │   │
│  │  - Container Management Dashboard                │   │
│  │  - Gateway Config Editor                         │   │
│  │  - MCP Inspector                                 │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          │
                          │ HTTPS/WebSocket
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Backend API (FastAPI/Python)                │
│                                                           │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │  Auth Service    │  │  Catalog Service │            │
│  │  - Session Mgmt  │  │  - Fetch & Cache │            │
│  │  - BW Integration│  │  - Search/Filter │            │
│  └──────────────────┘  └──────────────────┘            │
│                                                           │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │ Container Service│  │  Config Service  │            │
│  │  - CRUD Ops      │  │  - Gateway Config│            │
│  │  - Log Streaming │  │  - Secret Inject │            │
│  └──────────────────┘  └──────────────────┘            │
│                                                           │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │ Inspector Service│  │  Secret Manager  │            │
│  │  - MCP Protocol  │  │  - BW CLI Wrapper│            │
│  │  - Tools/Res/Pmt │  │  - Memory Cache  │            │
│  └──────────────────┘  └──────────────────┘            │
└─────────────────────────────────────────────────────────┘
                │                        │
                │                        │
                ▼                        ▼
┌──────────────────────┐    ┌──────────────────────┐
│   Docker Engine      │    │  Bitwarden Vault     │
│   - Container CRUD   │    │  - API/CLI Access    │
│   - Log Streaming    │    │  - Secret Storage    │
└──────────────────────┘    └──────────────────────┘
```

### 技術スタック

- **フロントエンド**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS
- **バックエンド**: Python 3.11+, FastAPI, Pydantic
- **Docker統合**: Docker SDK for Python
- **Bitwarden統合**: Bitwarden CLI (`bw`) または Bitwarden SDK
- **状態管理**: React Context API + SWR (データフェッチング)
- **通信**: REST API + WebSocket (ログストリーミング用)

## コンポーネントとインターフェース

### 1. フロントエンドコンポーネント

#### 1.1 認証モジュール (`/app/auth`)

**責務**: Bitwardenアカウントを使用したログイン/ログアウト

**主要コンポーネント**:
- `LoginForm`: APIキーまたはマスターパスワード入力フォーム
- `SessionProvider`: セッション状態の管理とContext提供
- `ProtectedRoute`: 認証が必要なページのラッパー

**API呼び出し**:
```typescript
POST /api/auth/login
  Body: { method: "api_key" | "master_password", credentials: {...} }
  Response: { session_id: string, expires_at: string }

POST /api/auth/logout
  Response: { success: boolean }

GET /api/auth/session
  Response: { valid: boolean, expires_at: string }
```

#### 1.2 Catalogブラウザ (`/app/catalog`)

**責務**: 利用可能なMCPサーバーの一覧表示と検索

**主要コンポーネント**:
- `CatalogList`: サーバーカードのグリッド表示
- `SearchBar`: キーワード検索とカテゴリフィルター
- `ServerCard`: 個別サーバー情報の表示とInstallボタン

**API呼び出し**:
```typescript
GET /api/catalog?source={url}
  Response: { servers: Array<CatalogItem> }

GET /api/catalog/search?q={keyword}&category={cat}
  Response: { servers: Array<CatalogItem> }
```

**データ型**:
```typescript
interface CatalogItem {
  id: string;
  name: string;
  description: string;
  category: string;
  docker_image: string;
  default_env: Record<string, string>;
  required_secrets: string[];
}
```

#### 1.3 コンテナ管理ダッシュボード (`/app/containers`)

**責務**: コンテナのライフサイクル管理とステータス監視

**主要コンポーネント**:
- `ContainerList`: 全コンテナの一覧とステータス表示
- `ContainerActions`: 起動/停止/再起動/削除ボタン
- `LogViewer`: リアルタイムログ表示（WebSocket）
- `ContainerConfigurator`: 新規起動設定フォーム

**API呼び出し**:
```typescript
GET /api/containers
  Response: { containers: Array<ContainerInfo> }

POST /api/containers
  Body: { config: ContainerConfig }
  Response: { container_id: string }

POST /api/containers/{id}/start
POST /api/containers/{id}/stop
POST /api/containers/{id}/restart
DELETE /api/containers/{id}

WebSocket /api/containers/{id}/logs
  Stream: { timestamp: string, message: string, stream: "stdout"|"stderr" }
```

#### 1.4 Gateway Config エディター (`/app/config`)

**責務**: Gateway設定ファイルのGUI編集

**主要コンポーネント**:
- `ConfigForm`: 設定項目の入力フォーム
- `SecretReferenceInput`: Bitwarden参照記法のサポート付き入力欄
- `ConfigValidator`: リアルタイムバリデーション表示

**API呼び出し**:
```typescript
GET /api/config/gateway
  Response: { config: GatewayConfig }

PUT /api/config/gateway
  Body: { config: GatewayConfig }
  Response: { success: boolean }
```

#### 1.5 MCP Inspector (`/app/inspector`)

**責務**: 起動中のMCPサーバーの機能解析

**主要コンポーネント**:
- `InspectorPanel`: Tools/Resources/Promptsのタブ表示
- `ToolsList`: 利用可能なToolsの一覧
- `ResourcesList`: 利用可能なResourcesの一覧
- `PromptsList`: 利用可能なPromptsの一覧

**API呼び出し**:
```typescript
GET /api/inspector/{container_id}/tools
  Response: { tools: Array<ToolInfo> }

GET /api/inspector/{container_id}/resources
  Response: { resources: Array<ResourceInfo> }

GET /api/inspector/{container_id}/prompts
  Response: { prompts: Array<PromptInfo> }
```

### 2. バックエンドサービス

#### 2.1 Auth Service (`services/auth.py`)

**責務**: Bitwarden認証とセッション管理

**主要メソッド**:
```python
class AuthService:
    async def login(self, method: str, credentials: dict) -> Session
    async def logout(self, session_id: str) -> bool
    async def validate_session(self, session_id: str) -> bool
    async def get_vault_access(self, session_id: str) -> VaultAccess
```

**セッション管理**:
- セッションIDはUUID v4で生成
- Redis（または in-memory dict）にセッション情報を保存
- デフォルトタイムアウト: 30分（非アクティブ時）
- セッション情報には、Bitwarden CLIのセッションキーを含む

#### 2.2 Secret Manager (`services/secrets.py`)

**責務**: Bitwarden参照記法の解決とキャッシング

**主要メソッド**:
```python
class SecretManager:
    async def resolve_reference(self, reference: str, session_id: str) -> str
    async def resolve_all(self, config: dict, session_id: str) -> dict
    def parse_reference(self, reference: str) -> tuple[str, str]  # (item_id, field)
    async def get_from_cache(self, key: str, session_id: str) -> Optional[str]
    async def set_cache(self, key: str, value: str, session_id: str) -> None
```

**参照記法の解析**:
- パターン: `{{ bw:item-id:field }}`
- 例: `{{ bw:a1b2c3d4:password }}` → Bitwardenのアイテム `a1b2c3d4` の `password` フィールド

**キャッシュ戦略**:
- キャッシュキー: `{session_id}:{item_id}:{field}`
- TTL: セッション終了まで（メモリ内のみ）
- ディスクへの永続化は一切行わない

#### 2.3 Container Service (`services/containers.py`)

**責務**: Dockerコンテナの管理

**主要メソッド**:
```python
class ContainerService:
    async def list_containers(self) -> List[ContainerInfo]
    async def create_container(self, config: ContainerConfig, session_id: str) -> str
    async def start_container(self, container_id: str) -> bool
    async def stop_container(self, container_id: str) -> bool
    async def restart_container(self, container_id: str) -> bool
    async def delete_container(self, container_id: str) -> bool
    async def stream_logs(self, container_id: str) -> AsyncIterator[LogEntry]
```

**コンテナ起動フロー**:
1. `ContainerConfig` を受け取る
2. 環境変数内のBitwarden参照を `SecretManager.resolve_all()` で解決
3. 解決済み環境変数でDockerコンテナを作成
4. コンテナを起動
5. コンテナIDを返す

#### 2.4 Catalog Service (`services/catalog.py`)

**責務**: Catalogデータの取得とキャッシング

**主要メソッド**:
```python
class CatalogService:
    async def fetch_catalog(self, source_url: str) -> List[CatalogItem]
    async def search_catalog(self, query: str, category: Optional[str]) -> List[CatalogItem]
    async def get_cached_catalog(self, source_url: str) -> Optional[List[CatalogItem]]
    async def update_cache(self, source_url: str, items: List[CatalogItem]) -> None
```

**Catalogフォーマット（JSON）**:
```json
{
  "version": "1.0",
  "servers": [
    {
      "id": "mcp-server-example",
      "name": "Example MCP Server",
      "description": "An example MCP server",
      "category": "utilities",
      "docker_image": "example/mcp-server:latest",
      "default_env": {
        "PORT": "8080",
        "API_KEY": "{{ bw:example-item:api_key }}"
      },
      "required_secrets": ["API_KEY"]
    }
  ]
}
```

#### 2.5 Inspector Service (`services/inspector.py`)

**責務**: MCPプロトコルを使用したサーバー機能の解析

**主要メソッド**:
```python
class InspectorService:
    async def connect_to_mcp(self, container_id: str) -> MCPConnection
    async def list_tools(self, container_id: str) -> List[ToolInfo]
    async def list_resources(self, container_id: str) -> List[ResourceInfo]
    async def list_prompts(self, container_id: str) -> List[PromptInfo]
```

**MCPプロトコル通信**:
- コンテナのネットワーク情報を取得
- MCPサーバーのエンドポイント（通常はHTTPまたはStdio）に接続
- `tools/list`, `resources/list`, `prompts/list` リクエストを送信
- レスポンスをパースして返す

#### 2.6 Config Service (`services/config.py`)

**責務**: Gateway設定ファイルの読み書き

**主要メソッド**:
```python
class ConfigService:
    async def read_gateway_config(self) -> GatewayConfig
    async def write_gateway_config(self, config: GatewayConfig) -> bool
    async def validate_config(self, config: GatewayConfig) -> ValidationResult
```

## データモデル

### Session
```python
class Session(BaseModel):
    session_id: str
    user_email: str
    bw_session_key: str  # Bitwarden CLIのセッションキー
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
```

### ContainerConfig
```python
class ContainerConfig(BaseModel):
    name: str
    image: str
    env: Dict[str, str]  # Bitwarden参照記法を含む可能性あり
    ports: Dict[str, int]
    volumes: Dict[str, str]
    labels: Dict[str, str]
```

### ContainerInfo
```python
class ContainerInfo(BaseModel):
    id: str
    name: str
    image: str
    status: Literal["running", "stopped", "error"]
    created_at: datetime
    ports: Dict[str, int]
```

### CatalogItem
```python
class CatalogItem(BaseModel):
    id: str
    name: str
    description: str
    category: str
    docker_image: str
    default_env: Dict[str, str]
    required_secrets: List[str]
```

### GatewayConfig
```python
class GatewayConfig(BaseModel):
    version: str
    servers: List[ServerConfig]
    global_settings: Dict[str, Any]

class ServerConfig(BaseModel):
    name: str
    container_id: str
    enabled: bool
    config: Dict[str, Any]
```

### ToolInfo / ResourceInfo / PromptInfo
```python
class ToolInfo(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]

class ResourceInfo(BaseModel):
    uri: str
    name: str
    description: str
    mime_type: str

class PromptInfo(BaseModel):
    name: str
    description: str
    arguments: List[Dict[str, Any]]
```


## 正確性プロパティ

*プロパティとは、システムのすべての有効な実行において真であるべき特性または動作のことです。本質的には、システムが何をすべきかについての形式的な記述です。プロパティは、人間が読める仕様と機械で検証可能な正確性保証との橋渡しをします。*

### 認証とセッション管理

**プロパティ1: 認証成功時のセッション確立**
*任意の*有効なBitwarden認証情報に対して、認証が成功した場合、システムは有効なセッションIDとVaultアクセス権を返す必要があります。
**検証対象: 要件 1.1, 1.2**

**プロパティ2: 認証失敗時のセッション非確立**
*任意の*無効なBitwarden認証情報に対して、認証が失敗した場合、システムはセッションを確立せず、エラーメッセージを返す必要があります。
**検証対象: 要件 1.3**

**プロパティ3: セッションタイムアウト**
*任意の*セッションに対して、最後のアクティビティから30分経過した場合、そのセッションは無効化され、Vaultアクセス権が破棄される必要があります。
**検証対象: 要件 1.4**

**プロパティ4: ログアウト時のセッション終了**
*任意の*アクティブなセッションに対して、ログアウトを実行した場合、そのセッションは即座に無効化され、Vaultアクセス権が破棄される必要があります。
**検証対象: 要件 1.5**

### 機密情報管理

**プロパティ5: Bitwarden参照記法の受け入れ**
*任意の*有効なBitwarden参照記法（`{{ bw:item-id:field }}`形式）に対して、システムはその記法を有効な入力として受け入れ、設定に保存する必要があります。
**検証対象: 要件 2.1, 2.5, 5.3**

**プロパティ6: 参照記法の解決**
*任意の*Bitwarden参照記法を含む環境変数に対して、コンテナ起動時にシステムはBitwarden Vaultから対応する値を取得し、環境変数に注入する必要があります。
**検証対象: 要件 2.2**

**プロパティ7: 無効な参照のエラーハンドリング**
*任意の*無効なBitwarden参照（存在しないアイテムIDやフィールド）に対して、システムはコンテナ起動を中止し、エラーメッセージを返す必要があります。
**検証対象: 要件 2.3**

**プロパティ8: 機密情報のディスク書き込み禁止**
*任意の*Bitwarden Vaultから取得したSecretに対して、システムはその値をディスク上のログファイルまたは設定ファイルに書き込んではなりません。
**検証対象: 要件 2.4, 7.3**

### Catalog管理

**プロパティ9: Catalogデータの取得**
*任意の*有効なCatalog URLに対して、システムはMCPサーバーのリストを取得し、各アイテムに名前、説明、Dockerイメージ、デフォルト環境変数を含める必要があります。
**検証対象: 要件 3.1, 3.4**

**プロパティ10: Catalog選択時の設定プレフィル**
*任意の*Catalogアイテムを選択した場合、システムは起動設定画面にそのアイテムの推奨設定（イメージ、環境変数）をプレフィルする必要があります。
**検証対象: 要件 3.3**

**プロパティ11: Catalog接続失敗時のフォールバック**
*任意の*Catalog URLへの接続が失敗した場合、システムはエラーメッセージを表示し、キャッシュされたデータが存在すればそれを表示する必要があります。
**検証対象: 要件 3.5**

### コンテナライフサイクル

**プロパティ12: コンテナ作成と起動**
*任意の*有効なコンテナ設定に対して、システムはDockerコンテナを作成し、起動し、コンテナIDを返す必要があります。
**検証対象: 要件 4.1**

**プロパティ13: コンテナ停止**
*任意の*実行中のコンテナに対して、停止操作を実行した場合、そのコンテナのステータスは「停止中」に変更される必要があります。
**検証対象: 要件 4.2**

**プロパティ14: コンテナ再起動**
*任意の*停止中のコンテナに対して、再起動操作を実行した場合、そのコンテナのステータスは「実行中」に変更される必要があります。
**検証対象: 要件 4.3**

**プロパティ15: コンテナ削除**
*任意の*コンテナに対して、削除操作を実行した場合、そのコンテナはシステムから削除され、コンテナ一覧に表示されなくなる必要があります。
**検証対象: 要件 4.4**

**プロパティ16: コンテナログの取得**
*任意の*実行中のコンテナに対して、システムはそのコンテナの標準出力と標準エラー出力を取得できる必要があります。
**検証対象: 要件 4.5**

### Gateway設定管理

**プロパティ17: 設定の読み込み**
*任意の*既存のGateway設定ファイルに対して、システムはその内容を正しく読み込み、表示できる必要があります。
**検証対象: 要件 5.1**

**プロパティ18: 設定のラウンドトリップ**
*任意の*有効なGateway設定に対して、保存してから再度読み込んだ場合、元の設定と同じ内容が得られる必要があります。
**検証対象: 要件 5.2**

**プロパティ19: 無効な設定の拒否**
*任意の*無効なGateway設定（必須フィールドの欠落、型の不一致など）に対して、システムは保存を拒否し、エラーメッセージを返す必要があります。
**検証対象: 要件 5.4**

**プロパティ20: 設定書き込み失敗のエラーハンドリング**
*任意の*設定保存操作において、ディスク書き込みに失敗した場合、システムはエラーメッセージを返す必要があります。
**検証対象: 要件 5.5**

### MCP Inspector

**プロパティ21: MCP機能情報の取得**
*任意の*実行中のMCPサーバーコンテナに対して、システムはTools、Resources、Promptsのリストを取得し、各項目に名前と説明を含める必要があります。
**検証対象: 要件 6.1, 6.2, 6.3, 6.5**

**プロパティ22: MCP接続失敗のエラーハンドリング**
*任意の*MCPサーバーへの接続が失敗した場合、システムはエラーメッセージを返す必要があります。
**検証対象: 要件 6.4**

### Secretキャッシング

**プロパティ23: Secretのキャッシング**
*任意の*Secretに対して、セッション期間中に同じSecretが2回要求された場合、2回目はBitwarden Vaultへの再アクセスなしにキャッシュから返される必要があります。
**検証対象: 要件 7.1, 7.4**

**プロパティ24: セッション終了時のキャッシュクリア**
*任意の*セッションに対して、セッション終了時にそのセッションに関連するすべてのキャッシュされたSecretが破棄される必要があります。
**検証対象: 要件 7.2**

**プロパティ25: キャッシュ有効期限**
*任意の*キャッシュされたSecretに対して、有効期限が切れた後に再度要求された場合、Bitwarden Vaultから再取得される必要があります。
**検証対象: 要件 7.5**

### Catalog検索とフィルタリング

**プロパティ26: キーワード検索**
*任意の*キーワードに対して、検索結果のすべてのアイテムは名前または説明にそのキーワードを含む必要があります。
**検証対象: 要件 8.1**

**プロパティ27: カテゴリフィルタリング**
*任意の*カテゴリに対して、フィルタリング結果のすべてのアイテムはそのカテゴリに属する必要があります。
**検証対象: 要件 8.2**

**プロパティ28: 検索リセット**
*任意の*検索状態に対して、検索ボックスをクリアした場合、すべてのCatalogアイテムが再表示される必要があります。
**検証対象: 要件 8.4**

**プロパティ29: 複合フィルタリング**
*任意の*複数のフィルター条件に対して、結果のすべてのアイテムはすべての条件を満たす必要があります。
**検証対象: 要件 8.5**

### コンテナステータス監視

**プロパティ30: ステータス表示**
*任意の*コンテナに対して、システムはその現在のステータス（実行中、停止中、エラー）を正しく取得し、表示する必要があります。
**検証対象: 要件 9.1**

**プロパティ31: エラー状態の強調表示**
*任意の*エラー状態のコンテナに対して、システムはそのコンテナを視覚的に強調表示する（特定のCSSクラスやスタイルを適用する）必要があります。
**検証対象: 要件 9.3**

**プロパティ32: コンテナ詳細情報の取得**
*任意の*コンテナに対して、システムは詳細情報（起動時刻、リソース使用状況）を取得できる必要があります。
**検証対象: 要件 9.4**

**プロパティ33: Docker通信失敗のエラーハンドリング**
*任意の*Dockerデーモンへの通信が失敗した場合、システムはエラーメッセージを返す必要があります。
**検証対象: 要件 9.5**

### エラーハンドリング

**プロパティ34: エラーメッセージの表示**
*任意の*エラーが発生した場合、システムはユーザーに分かりやすいエラーメッセージを返す必要があります。
**検証対象: 要件 10.1**

**プロパティ35: エラーメッセージの内容**
*任意の*エラーメッセージに対して、可能な限り具体的な原因情報を含める必要があります。
**検証対象: 要件 10.2**

**プロパティ36: 致命的エラーのロギング**
*任意の*致命的なエラーが発生した場合、システムはエラー詳細をバックエンドログに記録する必要があります。
**検証対象: 要件 10.5**

## エラーハンドリング

### エラーの分類

1. **認証エラー**
   - 無効な認証情報
   - Bitwarden APIへの接続失敗
   - セッションタイムアウト

2. **Vaultアクセスエラー**
   - 存在しないアイテムID
   - アクセス権限不足
   - ネットワークエラー

3. **Dockerエラー**
   - コンテナ作成失敗
   - イメージのプル失敗
   - Dockerデーモン接続失敗

4. **Catalogエラー**
   - Catalog URLへの接続失敗
   - 不正なCatalogフォーマット

5. **設定エラー**
   - 無効な設定値
   - ファイル読み書き失敗

### エラーハンドリング戦略

#### フロントエンド

- すべてのAPI呼び出しを `try-catch` でラップ
- エラーレスポンスから `error_code` と `message` を抽出
- ユーザーフレンドリーなメッセージに変換して表示
- トースト通知またはモーダルダイアログで表示

```typescript
try {
  const response = await fetch('/api/containers', { method: 'POST', body: config });
  if (!response.ok) {
    const error = await response.json();
    showError(error.message);
  }
} catch (error) {
  showError('ネットワークエラーが発生しました。接続を確認してください。');
}
```

#### バックエンド

- カスタム例外クラスを定義（`AuthError`, `VaultError`, `DockerError` など）
- FastAPIの例外ハンドラーでキャッチし、適切なHTTPステータスコードとメッセージを返す
- すべてのエラーをログに記録（機密情報は除く）

```python
class VaultError(Exception):
    def __init__(self, message: str, item_id: str):
        self.message = message
        self.item_id = item_id

@app.exception_handler(VaultError)
async def vault_error_handler(request: Request, exc: VaultError):
    logger.error(f"Vault access error: {exc.message} (item: {exc.item_id})")
    return JSONResponse(
        status_code=400,
        content={"error_code": "VAULT_ACCESS_ERROR", "message": exc.message}
    )
```

### リトライ戦略

- **Bitwarden API**: 一時的なネットワークエラーの場合、最大3回リトライ（指数バックオフ）
- **Docker API**: コンテナ起動失敗の場合、1回リトライ
- **Catalog取得**: 失敗時はキャッシュを使用、バックグラウンドで再試行

## テスト戦略

### 二重テストアプローチ

本システムでは、ユニットテストとプロパティベーステスト（PBT）の両方を使用します。これらは補完的であり、両方を含める必要があります：

- **ユニットテスト**: 特定の例、エッジケース、エラー条件を検証
- **プロパティテスト**: すべての入力にわたって保持されるべき普遍的なプロパティを検証

両者を組み合わせることで、包括的なカバレッジを提供します。ユニットテストは具体的なバグをキャッチし、プロパティテストは一般的な正確性を検証します。

### ユニットテスト

**フロントエンド（Jest + React Testing Library）**:
- コンポーネントのレンダリング
- ユーザーインタラクション（クリック、入力）
- 状態管理
- API呼び出しのモック

**バックエンド（pytest）**:
- 各サービスの主要メソッド
- エラーハンドリング
- エッジケース（空の入力、無効なデータなど）

例:
```python
def test_parse_bitwarden_reference():
    """Test parsing of Bitwarden reference notation"""
    secret_manager = SecretManager()
    item_id, field = secret_manager.parse_reference("{{ bw:abc123:password }}")
    assert item_id == "abc123"
    assert field == "password"

def test_parse_invalid_reference():
    """Test error handling for invalid reference"""
    secret_manager = SecretManager()
    with pytest.raises(ValueError):
        secret_manager.parse_reference("invalid")
```

### プロパティベーステスト

**ライブラリ**: Hypothesis（Python）、fast-check（TypeScript）

**要件**:
- 各プロパティベーステストは最低100回の反復を実行するように設定
- 各テストには、設計書の正確性プロパティを参照するコメントを明示的にタグ付け
- タグ形式: `**Feature: docker-mcp-gateway-console, Property {number}: {property_text}**`
- 各正確性プロパティは単一のプロパティベーステストで実装

例:
```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1), st.text(min_size=1))
def test_bitwarden_reference_roundtrip(item_id: str, field: str):
    """
    **Feature: docker-mcp-gateway-console, Property 5: Bitwarden参照記法の受け入れ**
    
    For any valid Bitwarden reference notation, the system should accept it
    and be able to parse it back to the original components.
    """
    secret_manager = SecretManager()
    reference = f"{{{{ bw:{item_id}:{field} }}}}"
    
    # Should accept the reference
    assert secret_manager.is_valid_reference(reference)
    
    # Should parse back to original values
    parsed_id, parsed_field = secret_manager.parse_reference(reference)
    assert parsed_id == item_id
    assert parsed_field == field
```

```typescript
import fc from 'fast-check';

describe('Catalog Search', () => {
  it('should only return items matching the keyword', () => {
    /**
     * **Feature: docker-mcp-gateway-console, Property 26: キーワード検索**
     * 
     * For any keyword, all search results should contain that keyword
     * in either the name or description.
     */
    fc.assert(
      fc.property(
        fc.array(catalogItemArbitrary()),
        fc.string({ minLength: 1 }),
        (items, keyword) => {
          const results = searchCatalog(items, keyword);
          return results.every(item => 
            item.name.includes(keyword) || item.description.includes(keyword)
          );
        }
      ),
      { numRuns: 100 }
    );
  });
});
```

### 統合テスト

- Docker統合: テスト用のDockerコンテナを実際に起動・停止
- Bitwarden統合: テスト用のVaultアカウントを使用（本番データは使用しない）
- E2Eテスト: Playwright を使用したブラウザ自動化

### テストデータ

- **モックデータ**: 開発・ユニットテスト用
- **テストVault**: Bitwarden統合テスト用の専用アカウント
- **テストCatalog**: 固定のテスト用Catalog JSON

### CI/CD

- すべてのプルリクエストでユニットテストとプロパティテストを実行
- 統合テストは夜間ビルドで実行
- カバレッジ目標: 80%以上

## セキュリティ考慮事項

### 機密情報の保護

1. **メモリ内のみで処理**
   - Secretは取得後、メモリ内でのみ保持
   - ディスクへの書き込みを一切行わない
   - ログ出力時にSecretをマスク

2. **セッション管理**
   - セッションIDはUUID v4で生成（推測不可能）
   - HTTPSのみでの通信を強制
   - セッションCookieに `HttpOnly`, `Secure`, `SameSite=Strict` を設定

3. **Bitwarden認証**
   - APIキー方式を推奨（2FAの複雑さを回避）
   - マスターパスワードはメモリ内でのみ処理、即座に破棄

### 入力検証

- すべてのユーザー入力をバリデーション
- Bitwarden参照記法の正規表現チェック
- Docker設定のスキーマ検証（Pydantic）

### アクセス制御

- 現バージョンでは単一ユーザーのみを想定
- 将来的には、ユーザーごとのVault分離を検討

## パフォーマンス最適化

### フロントエンド

- **コード分割**: Next.jsの動的インポートを使用
- **データフェッチング**: SWRによるキャッシングと再検証
- **仮想化**: 大量のCatalogアイテムを表示する際は仮想スクロール

### バックエンド

- **非同期処理**: FastAPIの非同期エンドポイントを活用
- **Catalogキャッシング**: 取得したCatalogデータをRedisまたはメモリにキャッシュ（TTL: 1時間）
- **Secretキャッシング**: セッション期間中、Secretをメモリにキャッシュ

### Docker

- **イメージのプリプル**: よく使うイメージを事前にプル
- **コンテナの再利用**: 可能な限りコンテナを停止・再起動で管理

## デプロイメント

### 推奨構成

- **開発環境**: Docker Compose で全サービスを起動
- **本番環境**: 
  - フロントエンド: Vercel または自己ホスト（Next.js standalone）
  - バックエンド: Docker コンテナ（FastAPI）
  - Dockerホスト: ローカルまたはリモートのDockerデーモン

### 環境変数

```bash
# Backend
BITWARDEN_CLI_PATH=/usr/local/bin/bw
DOCKER_HOST=unix:///var/run/docker.sock  # Standard: rootful Docker socket
                                          # Override for rootless: unix:///run/user/$UID/docker.sock
SESSION_TIMEOUT_MINUTES=30
CATALOG_CACHE_TTL_SECONDS=3600

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 依存関係

- Python 3.11+
- Node.js 18+
- Docker Engine 20.10+
- Bitwarden CLI 2023.x+

## 今後の拡張

### Phase 2（将来的な機能）

- **カスタムCatalogソース**: ユーザー独自のCatalog URLを追加
- **Bitwardenへの同期**: コンソール上で生成した設定をBitwardenのSecure Noteとして保存
- **マルチユーザー対応**: Bitwarden Organizationの共有機能への対応
- **通知機能**: コンテナのステータス変更をブラウザ通知
- **メトリクス収集**: コンテナのリソース使用状況のグラフ表示

### 技術的負債の管理

- 定期的なセキュリティ監査
- 依存関係の更新（Dependabot）
- パフォーマンスプロファイリング
