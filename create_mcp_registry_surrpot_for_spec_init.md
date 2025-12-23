# **1. 概要と目的**

既存の「Docker MCP Gateway Web Console」において、サーバーカタログの取得元として現在の `DockerMCPCatalog` に加え、`Official MCP Registry` を選択・利用できるように拡張する。

ユーザーがカタログソースのURLを手入力する手間を省くため、フロントエンドの入力フォームをセレクタ形式に変更し、プリセットされたソース（Docker / Official）を簡単に切り替えられるようにする。データ取得は既存のバックエンド処理を拡張し、レート制限回避とデータ変換をサーバーサイドで行う。

# **2. 技術スタック**

| 項目 | 内容 |
| --- | --- |
| 言語 | Python (FastAPI), TypeScript (Next.js) |
| フレームワーク | FastAPI, Next.js (App Router), Tailwind CSS |
| 開発形態 | 既存システムへの追加・改修 (Brownfield) |

# **3. 開発・テスト環境の制約 (重要)**

* **DevContainer要件**:
* 既存の `.devcontainer` 環境（`devcontainer.json`, `docker-compose.devcontainer.yml`）を開発・テスト環境として使用すること。


* **テスト実行ポリシー**:
* すべての自動テスト（Unit/Integration/E2E）は **DevContainer内でのみ** 実行すること。
* ホスト環境での直接実行は禁止する。
* `cc-sdd` ツール自体はホスト側で稼働させ、テスト実行コマンドは `docker exec` や `devcontainer exec` を経由する形式（例: `scripts/run-tests.sh` の利用）とすること。



# **4. 機能要件詳細**

### **4.1 フロントエンド改修 (Next.js)**

* **カタログソース選択UIの変更**:
* `frontend/app/catalog/page.tsx` のURL入力テキストボックスを `Select`（セレクタ）コンポーネントに置き換える。
* セレクタの選択肢として以下を用意する：
1. **Docker MCP Catalog**: `https://api.github.com/repos/docker/mcp-registry/contents/servers`
2. **Official MCP Registry**: `https://registry.modelcontextprotocol.io/mcp-registry.json`
3. **Custom URL**: 任意入力（選択時のみテキスト入力を許可）


* ソース選択が変更された際、自動的または「読み込み」ボタン押下で `fetchCatalog` を呼び出し、表示を更新する。



### **4.2 バックエンド改修 (FastAPI)**

* **CatalogService の拡張**:
* `backend/app/services/catalog.py` に、Official MCP Registry 形式の JSON をパースするロジックを正式に実装する。
* `_fetch_from_url` メソッドにおいて、レスポンスが Official Registry 形式（`mcp-registry.json`）の場合の分岐を追加する。
* 取得したデータを既存の `CatalogItem` モデルに変換して返す。特に `docker_image` や `required_envs` のマッピングを正確に行う。


* **キャッシュ管理の最適化**:
* 新しいソースURLに対しても、既存の `_cache` 機構 が正しく動作することを確認する。



### **4.3 APIエンドポイント**

* `GET /api/catalog` は、フロントエンドから渡される `source` パラメータに基づき、適切なパースロジックを選択してデータを返す。

# **5. その他の仕様**

* **エラーハンドリング**:
* 外部レジストリがダウンしている場合や、JSONのパースに失敗した場合は、既存の `CatalogError` を送出し、フロントエンドに分かりやすいエラーメッセージを表示する。


* **パフォーマンス**:
* GitHub APIを利用する際は、既存の `GitHubTokenService` を通じて認証ヘッダーを付与し、レート制限を回避する。


* **互換性**:
* 既存の Docker MCP Catalog 形式（ディレクトリ構造を再帰的にフェッチする形式）のサポートを維持すること。
