# Implementation Plan

## 1. データベーススキーマ拡張
- [x] 1.1 (P) remote_servers テーブルの追加
  - server_id (PK), catalog_item_id, name, endpoint, status, credential_key, last_connected_at, error_message, created_at カラムを定義
  - status は RemoteServerStatus Enum 値を格納（unregistered/registered/auth_required/authenticated/disabled/error）
  - credential_key は credentials テーブルへの外部参照（オプショナル）
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 1.2 (P) oauth_states テーブルの追加
  - state (PK), server_id, code_challenge, code_challenge_method, scopes, authorize_url, token_url, client_id, redirect_uri, expires_at, created_at カラムを定義
  - expires_at にインデックスを作成し、定期 GC で TTL 超過行を削除
  - code_verifier は Backend で保存せず、クライアント側でセッションストレージに短命保持
  - _Requirements: 3.2, 3.3, 4.1_

- [x] 1.3 (P) StateStore に is_endpoint_allowed メソッドを追加
  - REMOTE_MCP_ALLOWED_DOMAINS 環境変数を読み取り、ホスト名・ポート・ワイルドカードマッチングを実行
  - ポート指定なしのエントリはデフォルトポート（HTTPS=443, HTTP=80）のみ許可
  - IPv6 リテラルは明示的に拒否（セキュリティ理由：パース複雑性）
  - 空リストは deny-all（すべて False）
  - _Requirements: 8.3, 8.4_

## 2. CatalogService 拡張（リモートサーバー対応）
- [x] 2.1 CatalogItem モデル拡張
  - server_type (Optional[str]), remote_endpoint (Optional[HttpUrl]), is_remote (bool) フィールドを追加
  - oauth_config (Optional[dict]) フィールドを追加（リモートサーバー用 OAuth 設定）
  - docker_image が存在すれば優先、なければ remote_endpoint を使用する派生ロジックを実装
  - _Requirements: 1.1, 1.3_

- [x] 2.2 カタログフィルタロジックの更新
  - _filter_items_missing_image を「docker_image OR remote_endpoint が存在」に変更
  - remote_endpoint の URL 形式・スキーム検証を実施（不正な形式は除外し、警告ログに記録）
  - HTTPS 必須（ALLOW_INSECURE_ENDPOINT=true 時は localhost/http を一時許可）
  - REMOTE_MCP_ALLOWED_DOMAINS による許可リスト検証は CatalogService では実施せず、RemoteMcpService で実施
  - _Requirements: 1.1, 1.2, 8.1, 8.2_

## 3. OAuthService 拡張（state 永続化・PKCE 対応）
- [x] 3.1 state 永続化ロジックの実装
  - _persist_state メソッドを追加し、state, server_id, code_challenge, OAuth設定を oauth_states テーブルに保存
  - TTL (10分) を expires_at に設定し、定期 GC で削除
  - state 検証時にタイムスタンプをチェックし、有効期限外は CSRF 試行として拒否
  - 検証成功後、当該 state を即座に無効化し、再利用を防止
  - _Requirements: 3.2, 3.3, 4.1, 4.2_

- [x] 3.2 PKCE フローの実装
  - POST /api/oauth/start で server_id と code_challenge を受け取り、server_id から OAuth 設定を取得
  - code_challenge_method は "S256" 固定（SHA-256）
  - POST /api/oauth/callback で code, state, code_verifier を受け取り、code_verifier と保存された code_challenge の整合性を確認
  - OAuth Provider へトークン交換リクエスト（code, code_verifier を送信）
  - 取得したトークンを server_id に紐付けて credentials テーブルに保存
  - _Requirements: 3.2, 3.4, 3.5, 3.6, 3.7, 4.3, 4.4, 4.5_

- [x] 3.3 OAuth API エンドポイントの実装
  - POST /api/oauth/start: server_id, code_challenge を受け取り、auth_url, state を返却
  - POST /api/oauth/callback: code, state, code_verifier を受け取り、トークン取得・保存後に success: true を返却
  - エラーハンドリング: 400 (不正リクエスト), 401 (トークン交換拒否), 404 (server_id 不存在), 500 (内部エラー)
  - _Requirements: 3.1, 3.8, 4.1, 4.2, 4.3, 4.4_

## 4. RemoteMcpService の実装
- [x] 4.1 RemoteMcpService サービス層の基盤実装
  - RemoteServerStatus Enum と RemoteServerRecord モデルを定義
  - StateStore への依存注入と remote_servers テーブルへの CRUD 操作を実装
  - OAuthService への依存注入と credential 取得・検証ロジックを実装
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 4.2 (P) サーバー登録・削除ロジックの実装
  - register_server: catalog_item_id から endpoint を取得し、is_endpoint_allowed で検証後、remote_servers に保存
  - 不許可エンドポイントの場合、HTTP 400 Bad Request を返却し、監査ログに記録
  - 重複登録時は HTTP 409 Conflict を返却
  - delete_server: delete_credentials フラグに応じて credentials テーブルから認証情報を削除
  - _Requirements: 2.1, 2.3, 2.5, 2.6, 8.3, 8.4, 9.1, 9.2_

- [x] 4.3 (P) サーバー有効化・無効化ロジックの実装
  - enable_server: 認証が必要な場合は status=auth_required に設定
  - disable_server: status=disabled に更新し、ランタイム統合を停止
  - 状態遷移の監査ログ記録
  - _Requirements: 2.4, 2.5, 9.2_

- [x] 4.4 SSE 接続管理の実装
  - MCP Python SDK の sse_client() をラップし、接続確立タイムアウト（30秒）を設定
  - httpx.AsyncClient で SSE 接続の HTTP レイヤータイムアウトを設定
  - Heartbeat (120秒ごとに MCP ping) とアイドルタイムアウト（連続300秒無応答で切断）を実装
  - 同時接続数上限（開発環境 5、本番環境 20）を asyncio.Semaphore で制御
  - 上限超過時は HTTP 429 (Too Many Requests) を返却
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 4.5 接続・接続テスト API の実装
  - POST /api/remote-servers/{id}/connect: credential 復号後、SSE 接続を確立し、capabilities を返却
  - POST /api/remote-servers/{id}/test: 到達性と認証状態を確認し、結果を返却
  - 不許可エンドポイントへの接続試行は HTTP 400 を返却し、監査ログに記録
  - _Requirements: 6.1, 6.5, 8.3, 8.4, 9.3_

- [x] 4.6 (P) Remote Servers API エンドポイントの実装
  - GET /api/remote-servers: 登録済みサーバー一覧を返却
  - POST /api/remote-servers: catalog_item_id を受け取り、サーバーを登録
  - GET /api/remote-servers/{id}: サーバー詳細を返却
  - POST /api/remote-servers/{id}/enable, /disable: サーバーを有効化・無効化
  - DELETE /api/remote-servers/{id}: サーバーを削除（delete_credentials オプション対応）
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

## 5. フロントエンド UI の実装
- [x] 5.1 RemoteServerList コンポーネントの実装
  - SWR で /api/remote-servers からサーバー一覧を取得
  - status によるバッジ表示（未登録/要認証/認証済み/エラー）
  - 検索・フィルタ機能の実装
  - _Requirements: 1.1, 1.2, 7.1_

- [ ] 5.2 RemoteServerDetail コンポーネントの実装
  - サーバー詳細表示（名称、提供元、説明、接続先エンドポイント、認証要否、要求スコープ、想定トランスポート）
  - 「認証開始」ボタン: クライアント側で code_verifier を生成し、code_challenge を計算して /api/oauth/start に送信
  - 取得した auth_url へリダイレクト、state と code_verifier をセッションストレージに保存
  - OAuth コールバック処理: URL クエリパラメータから code と state を取得し、セッションストレージから code_verifier を取得して /api/oauth/callback に送信
  - 「接続テスト」ボタン: /api/remote-servers/{id}/test を呼び出し、結果を表示
  - 進行中状態のスピナー表示
  - _Requirements: 1.3, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.8, 7.2, 7.3, 7.4, 7.5_

- [ ] 5.3 (P) OAuth コールバックページの実装
  - OAuth Provider からのリダイレクトを受け取り、code と state を抽出
  - セッションストレージから code_verifier を取得し、/api/oauth/callback に送信
  - 認証完了後、サーバー詳細画面へリダイレクト
  - エラー時は失敗理由を表示し、再試行手段を提供
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 7.4_

- [ ] 5.4 (P) カタログ UI の更新
  - リモートサーバー（is_remote=true）の表示対応
  - Docker サーバーとリモートサーバーの区別表示
  - カタログ取得失敗時の再試行手段と最後に成功したデータの閲覧機能
  - _Requirements: 1.1, 1.2, 1.4, 1.5_

## 6. セキュリティ・監査機能の実装
- [ ] 6.1 (P) クレデンシャル暗号化の実装
  - OAuth トークンを Fernet で暗号化して credentials テーブルに保存
  - OS ネイティブのセキュアストアが利用できない場合、AES-256-GCM で暗号化
  - マスターキーは環境変数 CREDENTIAL_ENCRYPTION_KEY から読み込み
  - ログおよびエラー応答に認証情報を含めない
  - _Requirements: 5.1, 5.2, 5.3, 5.6_

- [ ] 6.2 (P) 認証情報削除機能の実装
  - ユーザーが認証解除を実行した際、当該サーバーに紐づく保存済みトークンを利用不能にする
  - 認証情報の有無と紐づくサーバーを Web Console で確認できるように表示
  - _Requirements: 4.7, 5.4, 5.5_

- [ ] 6.3 (P) 監査ログとメトリクスの実装
  - server_registered, server_authenticated, connection_failed, endpoint_rejected イベントを audit_logs に記録
  - remote_server_connections_total, remote_server_connections_rejected_total, oauth_flow_success_total, oauth_flow_failure_total メトリクスを記録
  - 許可リスト検証によるアクセス拒否時の監査ログ記録
  - _Requirements: 8.4, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5_

## 7. エラーハンドリングと復旧機能
- [ ] 7.1 (P) エラーハンドリングの実装
  - ネットワークエラー時のユーザー識別可能なエラー情報返却
  - 外部サービス不安定時の再試行手段提供
  - 認証失効・不足時のリクエスト拒否と再認証誘導
  - 無効化操作時の当該サーバーへの中継停止（他サーバーへの影響なし）
  - 重大な失敗時の登録情報整合性保持
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

## 8. テストの実装
- [ ] 8.1 (P) StateStore.is_endpoint_allowed のユニットテスト
  - 完全一致マッチング、ポート番号明示マッチング、ワイルドカードマッチング、IPv6 拒否、空リスト deny-all のテストケース
  - _Requirements: 8.3, 8.4_

- [ ] 8.2 (P) RemoteMcpService のユニットテスト
  - register_server: 正常登録、重複拒否、allowlist 検証（許可/不許可エンドポイント）
  - connect: credential 復号、SSE 接続モック、allowlist 検証（許可/不許可エンドポイント）
  - _Requirements: 2.1, 2.3, 6.1, 8.3, 8.4_

- [ ] 8.3 (P) OAuthService のユニットテスト
  - _persist_state: server_id を渡し、oauth_states に正しく保存されることを確認
  - _validate_state: state から server_id を取得できることを確認、存在しない server_id での OAuth 開始は HTTP 404 を返却
  - TTL 検証と server_id 紐付け
  - _Requirements: 3.2, 3.3, 4.1, 4.2_

- [ ] 8.4 (P) CatalogService のユニットテスト
  - docker_image 優先ロジック（両方存在時）
  - remote_endpoint 単独時の is_remote=True 設定
  - HTTPS スキーム検証（ALLOW_INSECURE_ENDPOINT=false 時）
  - 開発環境での localhost/http 許可（ALLOW_INSECURE_ENDPOINT=true 時）
  - 不正な URL 形式のアイテム除外
  - _Requirements: 1.1, 1.2, 8.1, 8.2_

- [ ] 8.5 (P) OAuth フロー統合テスト
  - リモートサーバー登録 → OAuth 開始 → OAuth Provider からコールバック（モック） → OAuth コールバック処理 → トークン取得・保存確認
  - server_id に紐付いた credential が正しく保存されていることを検証
  - _Requirements: 2.1, 3.1, 3.2, 3.8, 4.1, 4.3, 4.5_

- [ ] 8.6 (P) リモートサーバー接続統合テスト
  - リモートサーバー登録 → 認証 → 接続テスト
  - カタログ取得 → リモートサーバーフィルタリング
  - _Requirements: 1.1, 2.1, 6.1, 6.5_

- [ ] 8.7 (P) Allowlist 統合テスト
  - REMOTE_MCP_ALLOWED_DOMAINS 設定変更 → 新規登録・接続の可否確認
  - ワイルドカードエントリでの登録・接続フロー
  - 不許可ドメインへの登録試行 → HTTP 400 + 監査ログ検証
  - _Requirements: 8.3, 8.4, 9.4_

- [ ]*8.8 E2E/UI テスト
  - リモートサーバー一覧表示
  - 認証開始 → OAuth リダイレクト → コールバック処理
  - 接続テスト実行と結果表示
  - _Requirements: 1.1, 1.2, 1.3, 3.1, 3.8, 6.5, 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ]*8.9 パフォーマンス/負荷テスト
  - 同時 OAuth フロー: 10 並列（認証フロー処理能力の検証）
  - SSE 接続負荷テスト: 開発環境 5 並列、本番環境 20 並列（上限検証 + リソース監視）
  - 接続上限超過テスト: 上限+1 接続時に HTTP 429 返却を確認
  - _Requirements: 6.1, 6.4_

## 9. マイグレーションと統合
- [ ] 9.1 データベースマイグレーションの実装
  - Phase 1: StateStore スキーマ追加（remote_servers, oauth_states）— 既存テーブルへの影響なし
  - Phase 2: CatalogItem モデル拡張（オプショナルフィールド追加）— 後方互換
  - Phase 3: OAuthService state 永続化 — メモリ管理と並行稼働
  - IF NOT EXISTS パターンでロールバック可能性を確保
  - _Requirements: 2.1, 3.2, 3.3_

- [ ] 9.2 環境変数とドキュメントの更新
  - REMOTE_MCP_ALLOWED_DOMAINS, REMOTE_MCP_MAX_CONNECTIONS, ALLOW_INSECURE_ENDPOINT の追加
  - 開発環境・本番環境の推奨設定例をドキュメントに記載
  - _Requirements: 8.1, 8.2, 8.3_

- [ ] 9.3 システム統合とエンドツーエンド検証
  - フロントエンド UI → Backend API → RemoteMcpService → MCP SDK の全体フロー検証
  - OAuth 認証フロー全体の動作確認
  - エラーハンドリングと復旧機能の検証
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 3.1, 4.1, 6.1, 7.1, 10.1, 10.2, 10.3, 10.4, 10.5_
