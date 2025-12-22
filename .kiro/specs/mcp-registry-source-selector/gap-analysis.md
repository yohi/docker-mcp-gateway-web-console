# Gap Analysis: mcp-registry-source-selector

## 1. Current State Investigation

### Frontend
- **Current UI**: `frontend/app/catalog/page.tsx` には `Catalog Source URL` を入力するテキストフィールドが実装されており、任意のURLを入力可能。
- **Component**: `CatalogList` コンポーネントおよび `lib/api/catalog.ts` の `fetchCatalog` は URL 文字列を `source` パラメータとしてバックエンドに送信している。
- **State**: ソース URL はローカルステート (`useState`) で管理され、デフォルト値は `DEFAULT_CATALOG_URL` (環境変数またはハードコードされたGitHub URL) が使用される。

### Backend
- **API Endpoint**: `GET /api/catalog` (`backend/app/api/catalog.py`) は `source` クエリパラメータを受け取る。
- **Behavior**: `source` パラメータは URL として解釈され、そのまま `CatalogService.fetch_catalog` に渡される。指定がない場合は `settings.catalog_default_url` が使用される。
- **Service Layer**: `CatalogService` (`backend/app/services/catalog.py`) は URL からデータをフェッチし、キャッシュ制御を行う。
- **Data Parsing**: `backend/app/services/catalog.py` 内に `_convert_explore_server` メソッドが存在し、`registry.modelcontextprotocol.io` 形式を含む複数のフォーマットに対応しようとしている形跡がある。 `docker/mcp-registry` (GitHub Contents API) 形式の処理も実装済み。
- **Configuration**: `backend/app/config.py` に `catalog_default_url` が定義されているが、"Official MCP Registry" 用の URL 設定や、ソースエイリアス ("docker", "official") の定義は存在しない。

## 2. Requirements Feasibility Analysis

### Missing Capabilities (Gaps)
1.  **Frontend Source Selector**:
    - **Current**: 自由入力のテキストフィールド。
    - **Required**: プリセット ("Docker", "Official") を選択する UI (Select/Radio)。
2.  **Backend Source Validation & Mapping**:
    - **Current**: `source` パラメータを URL として扱い、バリデーションは URL 形式チェックのみ。
    - **Required**: `source` パラメータを ID ("docker", "official") として扱い、バックエンド側で定義された信頼できる URL にマッピングするロジック。
    - **Security**: 任意の URL からのフェッチを禁止し、プリセットのみに制限する仕組みが必要。
3.  **Official Registry Configuration**:
    - **Current**: Official Registry の URL が設定ファイル (`config.py`) に定義されていない。
    - **Required**: `OFFICIAL_MCP_REGISTRY_URL` (仮) の追加。

### Research Needed
- **Official Registry URL & Schema**: `_convert_explore_server` メソッドが現在の Official Registry のレスポンス形式と完全に互換性があるか確認が必要。特に "Official MCP Registry" の正確なエンドポイント URL を確定させる必要がある (例: `https://github.com/modelcontextprotocol/registry` の `registry.json` なのか、API なのか)。

## 3. Implementation Approach Options

### Option A: Extend Existing Components (Recommended)
既存の `CatalogPage` と `CatalogService` を拡張して対応する。

- **Frontend**:
    - `frontend/app/catalog/page.tsx`: テキスト入力を `<select>` またはカスタム Select コンポーネントに置き換える。
    - `frontend/lib/api/catalog.ts`: API 呼び出し時に URL ではなく ID を送信するように変更する (API仕様の合意による)。
- **Backend**:
    - `backend/app/config.py`: `CATALOG_SOURCES` 定数 (辞書型) を定義し、ID と URL のマッピングを管理。
    - `backend/app/api/catalog.py`: `source` パラメータが URL か ID かを判定、あるいは ID 必須に変更し、`CATALOG_SOURCES` に基づいて URL を解決。未知の `source` の場合は 400 Bad Request を返す。
- **Data Processing**:
    - `CatalogService` の既存変換ロジックを必要に応じて調整。

**Trade-offs**:
- ✅ 既存のデータフローを維持し、最小限の変更で実現可能。
- ✅ 既存のキャッシュ機構 (`source_url` キー) をそのまま利用可能。
- ❌ API の後方互換性 (既存クライアントが URL を送ってきている場合) に配慮が必要だが、Web Console は自己完結しているため影響は限定的。

### Option B: New Components & Service Wrapper
カタログソース管理専用のクラスやコンポーネントを新設する。

- **Frontend**: `CatalogSourceSelector` コンポーネントを新規作成。
- **Backend**: `CatalogSourceManager` クラスを作成し、ソースの定義と解決を責務とする。

**Trade-offs**:
- ✅ 責務が明確になる。
- ❌ 現状の機能規模に対してオーバーエンジニアリングになる可能性がある。

推薦案は **Option A**。現在のコードベースはシンプルであり、既存コンポーネントの拡張で十分に保守性を維持できる。

## 4. Implementation Complexity & Risk

- **Effort**: **S (1-3 days)**
    - フロントエンドの UI 変更は軽微。
    - バックエンドのロジック変更もマッピング層の追加とバリデーションのみで、既存のフェッチ/パースロジックを流用できる。
- **Risk**: **Low**
    - 既存のDockerカタログへの影響は最小限に抑えられる。
    - Official Registry のスキーマ解析で多少の調整が必要になる可能性がある程度。

## 5. Recommendations

1.  **Backend Implementation First**:
    - `config.py` に `OFFICIAL_MCP_REGISTRY_URL` を追加。
    - `api/catalog.py` で `source` パラメータの解釈を「URL優先」から「ID優先/プリセット限定」に変更。
    - セキュリティ要件に基づき、任意の URL フェッチ機能を無効化 (設定フラグ等で開発時のみ許可するなど柔軟性を持たせるかは検討)。
2.  **Frontend Update**:
    - `CatalogPage` の入力フォームをドロップダウンに変更。
    - API 呼び出し時に `source=docker` または `source=official` を送信するように修正。
3.  **Validation**:
    - Official Registry の実際のデータを取得し、パースエラーが出ないか確認。

### Requirement-to-Asset Map
- **UI (Selector)**: `frontend/app/catalog/page.tsx` (Missing)
- **API (Source param)**: `backend/app/api/catalog.py` (Modify)
- **Config (Official URL)**: `backend/app/config.py` (Missing)
- **Logic (Schema Support)**: `backend/app/services/catalog.py` (Verify)
