# 実装計画

## タスク概要

本計画は、カタログソースのプリセット選択機能を実装するための段階的なタスクリストです。各タスクは自然言語で「何を実現するか」を記述し、実装の詳細は `design.md` を参照します。

---

## フェーズ 1: バックエンドの基盤整備

- [x] 1. カタログソースの型定義とバリデーション機能を実装する
- [x] 1.1 カタログソース識別子の列挙型を定義する
  - Docker と Official の2つのソースを識別可能にする
  - 文字列として扱える列挙型として定義する
  - バックエンドとフロントエンドで一貫した識別子を使用できるようにする
  - _Requirements: 2.1, 2.5, 5.1_

- [x] 1.2 構造化エラーコードと例外クラスを定義する
  - 無効なソース、レート制限、上流障害、内部エラーの各種エラーコードを定義する
  - エラーコード、メッセージ、再試行秒数を保持する例外クラスを作成する
  - エラーレスポンスのスキーマを定義する
  - _Requirements: 4.1, 4.2_

- [x] 2. 環境設定にOfficial MCP Registry URLを追加する
- [x] 2.1 設定クラスにOfficial Registry用のURL設定を追加する
  - Official MCP Registry のデフォルト URL を定義する
  - 環境変数による上書きをサポートする
  - 既存の Docker カタログ URL 設定を維持する（後方互換性）
  - _Requirements: 6.3_

- [x] 3. URL許可リスト検証機能を実装する
- [x] 3.1 許可されたURL以外へのアクセスを防止する検証器を作成する
  - 設定で定義されたカタログURL一覧を許可リストとして保持する
  - フェッチ前にURLが許可リスト内にあるか検証する機能を提供する
  - 許可リスト外のURLに対して構造化エラーを返す
  - URLは以下の正規化/検証ルールに従って比較する： (1) `http://example.com` と `http://example.com/` を同一視する、(2) `http`/`https` 以外（`file:`/`javascript:` 等）は拒否する、(3) デフォルトポート（80/443）は省略有無で一致判定する、(4) IPv6 アドレスは角括弧付き表記 `http://[::1]/` を基準に正規化して比較する
  - _Requirements: 5.1, 5.2_

---

## フェーズ 2: バックエンドAPIの拡張

- [ ] 4. カタログAPI エンドポイントを拡張する
- [ ] 4.1 sourceパラメータを受け付けてソースIDを解決する機能を追加する
  - source クエリパラメータを列挙型でバリデーションする
  - source クエリパラメータが完全に省略された場合は Docker をデフォルトとして扱い、後方互換性要件のため breaking-change フラグが有効化されない限りこの挙動を必須とする
  - ソースIDから対応するURLへ解決するロジックを実装する
  - source クエリパラメータが指定されていても未知/無効な値だった場合は error_code: invalid_source を含む構造化エラーレスポンスで 400 Bad Request を返す
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.2, 6.1_

- [ ] 4.2 構造化エラーレスポンスをHTTPレスポンスとして返却する
  - エラーコードに応じた適切なHTTPステータスコードを設定する（400/429/503/500）
  - 内部URL や認証情報をエラーメッセージに含めない
  - レート制限時は retry_after_seconds を含める
  - _Requirements: 4.1, 4.2, 5.4_

- [ ] 5. カタログサービスのエラーハンドリングを強化する
- [ ] 5.1 フェッチ前に許可リスト検証を実行する
  - URL検証器を呼び出してSSRFを防止する
  - 正規化済みURL同士で許可判定し、リクエスト送信時にも正規化結果を利用する（末尾スラッシュ、デフォルトポート、IPv6表記の揺れを吸収しつつ、`http/https` 以外は拒否）
  - 検証失敗時は構造化エラーをスローする
  - _Requirements: 5.1, 5.2_

- [ ] 5.2 上流レジストリのレート制限とタイムアウトに対応する
  - 上流が429を返した場合、Retry-Afterを抽出してレート制限エラーを返す
  - タイムアウトや5xxエラー時は上流障害エラーを返す
  - エラー情報を構造化してAPI層へ伝播する
  - _Requirements: 4.1, 4.2_

- [ ] 5.3 Official MCP Registry形式のJSONパースと変換を実装する
  - Official Registry から返されるスキーマを既存のCatalogItemモデルへマッピングする
  - マッピング不可能な項目は除外する
  - 未知のフィールドは無視する
  - 各アイテムに安定した識別子と表示名を保証する
  - gap-analysis.md で取得した Official MCP Registry 実データログをリプレイし、差分がないことを確認する
  - 具体例: Official Registry からの代表的なレスポンスを下記の通り想定する
    ```json
    {
      "name": "modelcontextprotocol/awesome-tool",
      "display_name": "Awesome Tool",
      "description": "高速なMCP対応AIツール",
      "homepage_url": "https://awesome.example.com",
      "tags": ["productivity"],
      "client": {
        "mcp": {
          "capabilities": ["call_tool"],
          "transport": {
            "type": "websocket",
            "url": "wss://awesome.example.com/mcp"
          }
        }
      }
    }
    ```
    あるいは tags/description が欠落するケース:
    ```json
    {
      "name": "modelcontextprotocol/minimal",
      "display_name": "Minimal MCP",
      "client": {
        "mcp": {
          "transport": {"type": "http", "url": "https://minimal.example.com/mcp"}
        }
      }
    }
    ```
  - フィールドマッピング: Official → CatalogItem
    | Official MCP Registry | 型 | CatalogItem | 型 | 備考 |
    | --- | --- | --- | --- | --- |
    | `name` | string | `id` | string | 未指定時は `display_name` を slug 化して代用、重複時は suffix を追加 |
    | `display_name` | string | `title` | string | 未指定時は `name` をそのまま利用 |
    | `description` | string/null | `description` | string | null/空は空文字列に正規化 |
    | `homepage_url` | string/url | `homepageUrl` | string | URL 文字列として格納、無効URLは破棄 |
    | `client.mcp.transport.url` | string/url | `endpoint` | string | `type` が websocket/http に応じてプロトコル属性を持たせる |
    | `tags` | string[] | `tags` | string[] | 文字列以外はスキップ |
    | `client.mcp.capabilities` | string[] | `capabilities` | string[] | 未指定時は空配列 |
  - 型不一致／欠落時の処理:
    1. 文字列フィールドが数値/配列の場合は文字列へ安全に変換できない限り、そのフィールドのみ破棄。
    2. URL フィールドは `http/https/ws/wss` のいずれかで始まらない場合は CatalogItem から除外。
    3. `name`/`display_name` の双方が欠落したアイテムは CatalogItem 自体を除外し、gap-analysis.md のバリデーション結果（「Official Registry: 2件の name 欠落」など）を参考にログへ警告を残す。
    4. `tags` や `capabilities` が配列以外の場合は空配列へフォールバック。
    5. 未知フィールドは保持せず、CatalogItem へコピーしない。
  - gap-analysis.md の Official データ検証結果を用いて、上記ルールが実データに適用されることを `pytest` ベースで確認する
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 6. 検索APIエンドポイントのsourceパラメータ対応を追加する
- [ ] 6.1 検索機能でもソース選択を可能にする
  - `/api/catalog/search` に source パラメータを追加する
  - `/api/catalog` と同様のソース解決とバリデーションを適用する
  - _Requirements: 2.1, 2.2, 2.5_

### 移行と将来拡張メモ
- カスタム URL の動的追加は `design.md` の Non-Goals で明示された通り本リリースの対象外だが、将来の拡張候補として backlog に残し、プリセット以外の許可ソースを追加する際は Requirement 5（`requirements.md`）で定義されたセキュリティ制約を維持する。
- `NEXT_PUBLIC_CATALOG_URL` を利用している既存デプロイ向けの移行手順:
  1. `.env.local` / `.env.production` などの環境ファイル、CI/CD シークレット、および `frontend` 配下で `NEXT_PUBLIC_CATALOG_URL` が参照されていないかを `grep -R "NEXT_PUBLIC_CATALOG_URL" frontend` などで確認し、現行値（Docker 既定 URL なのか、独自 Docker カタログなのか）を把握する。
  2. 本機能導入後はフロントエンドがプリセット ID（`docker` / `official`）のみ送信し、当該環境変数は無視されるため、値を削除し `CatalogSourceSelector` で必要なソースを選択する運用に切り替える。セキュリティ要件 (requirements.md Requirement 5) に沿い、任意 URL をクライアントから送らないようドキュメントにも注意書きを追記する。
  3. これまで `NEXT_PUBLIC_CATALOG_URL` で独自 Docker カタログを指定していた場合は、(a) 可能であれば `DockerMCPCatalog` もしくは `Official MCP Registry` 側にエントリを追加しプリセットへ統合する、(b) 統合が難しい間はバックエンドの `CATALOG_DEFAULT_URL`（`design.md` Migration Strategy で非推奨だが存続）を一時的なフォールバックとして上書きし、今後予定されているプリセット拡張またはカスタム URL 機能を待つ、のいずれかを選択する。
- 具体例およびチェックリストは `docs/migrations/mcp-registry-source-selector.md`（本タスクで追加予定）へリンクし、要件・設計とのトレーサビリティとセキュリティ上の理由を明記する。

---

## フェーズ 3: フロントエンドUI の実装

- [ ] 7. カタログソース選択UIコンポーネントを作成する
- [ ] 7.1 ソース選択セレクタコンポーネントを実装する
  - Docker と Official の2つのプリセットを選択可能なセレクタを作成する
  - フリーフォームのURL入力は提供しない
  - 選択変更時に親コンポーネントへコールバックを通知する
  - Tailwind CSSで既存UIと一貫したスタイリングを適用する
  - _Requirements: 1.1, 5.3_

- [ ] 8. カタログページでソース切替を管理する
- [ ] 8.1 ソース状態管理とリスト再取得の連携を実装する
  - デフォルトで Docker ソースを選択状態にする
  - ユーザーがソースを変更したらカタログリストを再取得する
  - ページリロードなしでソース切替を可能にする
  - エラー発生時も選択中のソースを保持する
  - _Requirements: 1.2, 1.3, 4.5, 6.2, 6.5_

- [ ] 9. カタログ一覧表示のエラーハンドリングを拡張する
- [ ] 9.1 構造化エラーコードに基づくエラー表示を実装する
  - error_code に応じて適切なエラーメッセージを表示する
  - レート制限時は retry_after_seconds のカウントダウンを表示する
  - 上流障害時は再試行ボタンを提供する
  - 取得中はローディング状態を表示する
  - _Requirements: 1.4, 1.5, 4.3, 4.4_

- [ ] 10. カタログAPI クライアントを拡張する
- [ ] 10.1 sourceパラメータをサポートする
  - カタログ取得関数に source パラメータを追加する
  - エラーレスポンスの型定義を追加する
  - 構造化エラーレスポンスをパースして型安全に扱う
  - _Requirements: 2.1_

---

## フェーズ 4: テストと検証

- [ ] 11. バックエンドの単体テストを実装する
- [ ] 11.1 ソース識別子と列挙型のバリデーションをテストする
  - 有効な値（docker、official）が受理されることを確認する
  - 無効な値が拒否されることを確認する
  - _Requirements: 2.1, 2.5_

- [ ] 11.2 ソースID解決ロジックをテストする
  - docker → Docker URL へのマッピングを確認する
  - official → Official URL へのマッピングを確認する
  - _Requirements: 2.3, 2.4_

- [ ] 11.3 URL許可リスト検証をテストする
  - 許可リスト内のURLが通過することを確認する
  - 許可リスト外のURLが拒否されることを確認する
  - URL正規化の等価性を検証する（例：`http://example.com` と `http://example.com/`、`example.com` と `example.com:80` を同一と扱う）
  - プロトコル検証を網羅する（`file:` や `javascript:` などの非 `http/https` スキームを拒否し、`https` との比較も確認する）
  - IPv6 アドレス許可リスト（例：`http://[::1]/`）への一致判定と、異なる表記 (`http://[0:0:0:0:0:0:0:1]/` など) の拒否/許容ポリシーを確認する
  - デフォルト以外の明示ポート（例：`http://example.com:8080`）が許可リストに存在しない場合に拒否されること、および許可リストに登録された場合は一致することを検証する
  - _Requirements: 5.1, 5.2_

- [ ] 11.4 構造化エラー生成をテストする
  - 各エラーコードが正しく生成されることを確認する
  - retry_after_seconds が適切に設定されることを確認する
  - _Requirements: 4.1, 4.2_

- [ ] 11.5 Official Registry形式の変換ロジックをテストする
  - 正常なデータが正しく変換されることを確認する
  - マッピング不可能な項目が除外されることを確認する
  - 未知のフィールドが無視されることを確認する
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 12. バックエンドの統合テストを実装する
- [ ] 12.1 source=dockerでのエンドツーエンド動作をテストする
  - APIがDockerカタログを正しく返すことを確認する
  - キャッシュ動作を確認する
  - _Requirements: 2.3, 6.1_

- [ ] 12.2 source=officialでのエンドツーエンド動作をテストする
  - APIがOfficial Registryカタログを正しく返すことを確認する
  - スキーマ変換が正常に機能することを確認する
  - _Requirements: 2.4, 3.1_

- [ ] 12.3 sourceパラメータ省略時と無効値のエンドツーエンド動作をテストする
  - source未指定時にDockerカタログが返されることを確認し、breaking-changeフラグ未設定時は後方互換挙動として必須であることを検証する
  - sourceが無効値の場合に400 Bad Requestが返り、error_code: invalid_source を含む構造化エラーレスポンスになることを確認する
  - 既存クライアント互換性を確認する
  - _Requirements: 2.2, 2.5, 5.2, 6.1, 6.2_

- [ ] 12.4 不正なsource値でのエラーレスポンスをテストする
  - 400 Bad Requestが返されることを確認する
  - error_code: invalid_source が含まれることを確認する
  - 上流へのリクエストが発生しないことを確認する
  - _Requirements: 2.5, 5.2_

- [ ] 12.5 上流レート制限時の動作をテストする
  - 上流が429を返した場合、APIが429を返すことを確認する
  - error_code: rate_limited と retry_after_seconds が含まれることを確認する
  - _Requirements: 4.1_

- [ ] 12.6 上流タイムアウト時の動作をテストする
  - 上流がタイムアウトした場合、503 Service Unavailableが返されることを確認する
  - error_code: upstream_unavailable が含まれることを確認する
  - _Requirements: 4.2_

- [ ] 13. フロントエンドの単体テストを実装する
- [ ] 13.1 ソース選択セレクタのレンダリングをテストする
  - DockerとOfficialの選択肢が表示されることを確認する
  - 選択変更時にコールバックが呼ばれることを確認する
  - _Requirements: 1.1_

- [ ] 13.2 カタログページのソース状態管理をテストする
  - 初期状態でDockerが選択されていることを確認する
  - ソース変更時にカタログ再取得が発生することを確認する
  - エラー時も選択ソースが保持されることを確認する
  - _Requirements: 1.2, 1.3, 4.5_

- [ ] 13.3 エラー表示ロジックをテストする
  - 各error_codeに対応するメッセージが表示されることを確認する
  - レート制限時にカウントダウンが表示されることを確認する
  - 再試行ボタンが適切に表示されることを確認する
  - _Requirements: 1.5, 4.3, 4.4_

- [ ] 14. E2E/UIテストを実装する
- [ ] 14.1 Dockerソース選択時のカタログ表示をテストする
  - セレクタでDockerを選択した際にカタログが表示されることを確認する
  - ローディング状態が正常に動作することを確認する
  - _Requirements: 1.1, 1.2, 1.4_

- [ ] 14.2 Officialソース選択時のカタログ表示をテストする
  - セレクタでOfficialを選択した際にカタログが表示されることを確認する
  - ソース切替でページリロードが発生しないことを確認する
  - _Requirements: 1.1, 1.2, 6.5_

- [ ] 14.3 レート制限エラーのUI動作をテストする
  - レート制限エラー時にカウントダウンが表示されることを確認する
  - カウントダウン後に再試行が可能になることを確認する
  - _Requirements: 4.3_

- [ ] 14.4 上流障害エラーのUI動作をテストする
  - 上流障害時に再試行ボタンが表示されることを確認する
  - 再試行ボタンでカタログ再取得が行われることを確認する
  - _Requirements: 4.4_

---

## フェーズ 5: ドキュメント更新と統合

- [ ] 15. ドキュメントを更新する
- [ ] 15.1 環境変数のドキュメントを更新する
  - CATALOG_OFFICIAL_URL の追加と CATALOG_DEFAULT_URL の非推奨化を詳細に説明する
  - 移行ガイドを以下の観点で補強する
    - (1) **新旧マッピング表**：NEXT_PUBLIC_CATALOG_URL／CATALOG_OFFICIAL_URL／CATALOG_DEFAULT_URL の優先順位と読み替えルールを示す（例：`NEXT_PUBLIC_CATALOG_URL`> `CATALOG_OFFICIAL_URL`> `CATALOG_DEFAULT_URL` の順で解決し、未設定時のみ次優先へフォールバックする）
      | 新環境変数 | 旧環境変数 | 優先順位 | 読み替えルール |
      | --- | --- | --- | --- |
      | NEXT_PUBLIC_CATALOG_URL | （旧来の同名） | 1 | 既存値をそのまま利用。未設定の場合のみ 2 へ |
      | CATALOG_OFFICIAL_URL | 新規 | 2 | Official Registry 用。未設定または利用不能時は 3 へ |
      | CATALOG_DEFAULT_URL | 旧: Docker 用 | 3 | 段階的廃止対象。Docker カタログに限定して利用 |
    - (2) **設定例と手順**：ローカル開発（`.env.local`）と Docker/クラウド環境（`docker-compose`, Secrets Manager 等）それぞれの設定例、必要なビルド・デプロイ手順をステップで提示する
    - (3) **段階的移行手順**：検証→移行→切替→廃止の各フェーズで実施すべき作業（例：検証フェーズで並行設定を入れて Canary を実施、移行フェーズで Official URL を本番に投入、切替フェーズでデフォルトを Official 化、廃止フェーズで DEFAULT を削除）をステップバイステップで記述する
    - (4) **非推奨タイムライン**：非推奨開始日、非推奨終了日（廃止予定日）、互換性保証期間（例：開始日から 90 日）を明記する
    - (5) **方針説明**：最後に「既存環境変数は当面尊重する」方針と非推奨ポリシーの整合性（互換期間中はフォールバックを維持し、終了後に正式廃止する）を説明する一文を追加する
  - _Requirements: 6.3_

- [ ] 15.2 APIドキュメントを更新する
  - sourceパラメータの仕様を追加する
  - エラーレスポンスの構造を記載する
  - 使用例を追加する
  - _Requirements: 2.1, 4.1, 4.2_

- [ ] 16. 既存機能との統合を確認する
- [ ] 16.1 既存のカタログ機能が正常に動作することを確認する
  - 上記移行ガイドの内容が製品挙動と一致していることを検証し、ドキュメントのマッピング表・手順・タイムラインと実装のフォールバック順序が揃っていることを確認する
  - 既存ユーザーの環境変数設定が互換期間中は尊重され、NEXT_PUBLIC_CATALOG_URL の挙動が変わらない（優先順位 1 のまま）ことを確認する
  - ローカル／Docker 等クラウド環境の設定例どおりに構成した際に、Official Registry 不可時でも Docker ソースへ自動フォールバックすることを検証する
  - 非推奨開始日・終了日が実装上の feature flag や設定で管理され、タイムライン通りに切替可能であることを確認する
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

---

## 完了基準

すべてのタスクが完了し、以下が満たされた時点で本機能は完成とする：

1. ✅ バックエンドが source パラメータ経由で Docker / Official 両ソースを取得できることを、`cd backend && pytest tests/api/catalog/test_source_selector.py tests/integration/catalog -q --maxfail=1` の成功（失敗 0 件）と `cd backend && pytest --cov=app --cov-report=term-missing` で TOTAL 行カバレッジ 85%以上・error_code（invalid_source / rate_limited / upstream_unavailable / upstream_timeout）のテスト網羅率 100% を満たすことで証明する。
2. ✅ フロントエンドのセレクタ UI・ソース状態管理がページリロードなしで切り替わることを、`cd frontend && npm run test -- --coverage --runInBand` による statements/branches カバレッジ 80%以上（`components/catalog` と `contexts/SessionContext.tsx` を含む）および `CatalogSourceSelector` / `catalog/page` の Jest テストで Docker・Official 両方の選択肢とコールバック発火・エラー時の選択保持を検証することで保証する。
3. ✅ エラー表示・再試行 UX と統合動作を、`cd frontend && npm run test:e2e`（Playwright）で @docker-source / @official-source / @rate-limit / @upstream-failure シナリオのパス率 100%（失敗 0 件）を確認し、`docker compose -f docker-compose.test.yml run --rm frontend npm run test:e2e -- --grep "@smoke"` による互換性スモークテストが通過することで確認する。
4. ✅ 単体・統合・E2E を含むフルテストスイートが安定していることを、`.github/workflows/ci-tests.yml` / `.github/workflows/e2e-tests.yml` の最新実行が成功し、ローカルでも `cd backend && pytest --maxfail=1 --disable-warnings -q`、`cd frontend && npm run test`, `cd frontend && npm run test:e2e:headed --project chromium` がすべてグリーンであること、さらに `./scripts/capture-baseline.sh staging` を用いたステージングデプロイ後の互換性スモーク結果が HTTP 2xx（エラー率 0%）であることで担保する。
5. ✅ ドキュメントは `docs/ARCHITECTURE.ja.md` / `docs/CATALOG_SCHEMA*.md` / `README*.md` に sample request・response・migration notes（環境変数優先順位、段階的移行手順、非推奨タイムライン）を追記し、各エンドポイントの例と error_code 対応表を掲載、さらに Pull Request 上で API 担当 + フロントエンド担当の 2 名レビュー（GitHub reviewers）を取得して承認履歴を残す。
6. ✅ 後方互換性は `docs/mcp-registry-source-selector/env-matrix.csv`（環境変数組み合わせマトリクス）と `docs/mcp-registry-source-selector/deprecated-behaviors.md`（非推奨動作一覧）で網羅し、各行について `docker compose -f docker-compose.test.yml run --rm backend pytest tests/integration/test_backward_compat.py -m env_matrix` および `cd frontend && NEXT_PUBLIC_CATALOG_URL=<case> CATALOG_OFFICIAL_URL=<case> CATALOG_DEFAULT_URL=<case> npm run test:e2e -- --grep "@backcompat"` を実行して全ケース成功（失敗 0 件）・deprecated 挙動が回帰していないことを確認する。
