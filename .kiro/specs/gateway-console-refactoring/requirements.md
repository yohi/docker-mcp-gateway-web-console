# Requirements Document

## Introduction
本ドキュメントは `docker-mcp-gateway-web-console` の大規模リファクタリングに関する要件を定義する。主眼は、Redis を用いた状態管理によるステートレス化、Worker コンテナによる重い処理の非同期化、ならびにログ/鍵管理/SSRF 対策等のセキュリティ強化である。既存フロントエンドとの API コントラクトは維持する。

## Project Description (Input)
- Redis を導入し、セッション等の状態管理をインメモリから排除してステートレス化する
- Worker コンテナを追加し、Bitwarden CLI 等の重い処理を非同期タスクとして実行する
- 機密情報のログ出力防止、暗号化キー管理の厳格化、SSRF 対策を実施する
- 依存ライブラリの更新と、Config と Secrets の境界を明確化する
- DevContainer を導入し、統合開発環境とテスト実行ポリシーを標準化する

## Requirements

### Requirement 1: Redis によるセッション永続化とステートレス化
**Objective:** As a 運用者, I want バックエンドをステートレス化して水平スケールできる, so that 再起動や複数レプリカでもセッションが維持される

#### Acceptance Criteria
 
- **1.1** The Backend Service shall セッション状態をプロセス内メモリではなく Redis に保存する
- **1.2** When Backend Service が再起動したとき, the Backend Service shall セッションタイムアウトまで既存セッションを有効として扱う
- **1.3** When 複数の Backend Service インスタンスが同一セッションを扱うとき, the Backend Service shall Redis 上の状態を一貫して参照・更新する
- **1.4** If Redis が利用不能のとき, then the Backend Service shall 認証・セッション更新を拒否し、復旧可能なエラーメッセージを返す

### Requirement 2: Worker コンテナによる Bitwarden 処理の非同期化
**Objective:** As a 利用者, I want 重い Bitwarden 操作で UI/API 応答がブロックされない, so that 操作待ち時間とタイムアウトを削減できる

#### Acceptance Criteria

- **2.1** When ユーザーが Bitwarden 操作を要求したとき, the Backend Service shall 完了を待たずにジョブを受理し `job_id` を返す
- **2.2** The Worker Service shall キューに登録された Bitwarden 操作を非同期に実行する
- **2.3** When ユーザーが `job_id` の状態確認を要求したとき, the Backend Service shall 状態（queued/running/succeeded/failed）と結果（成功データまたは失敗理由）を返す
- **2.4** If ジョブ実行が失敗したとき, then the Backend Service shall 秘密情報を含まない失敗理由を返す

### Requirement 3: SecretManager キャッシュの Redis 移行
**Objective:** As a 利用者, I want Bitwarden 参照の待ち時間を抑えつつ安全に扱いたい, so that 連続操作時の体験を向上できる

#### Acceptance Criteria
 
- **3.1** When 秘密情報を取得したとき, the Backend Service shall セッションスコープで Redis にキャッシュできる
- **3.2** While セッションが有効な間, the Backend Service shall キャッシュが有効であれば Bitwarden への再アクセスを行わない
- **3.3** When セッションが終了したとき, the Backend Service shall 当該セッションのキャッシュを Redis から削除する
- **3.4** The Backend Service shall 秘密情報を平文で永続ストレージに保存しない

### Requirement 4: ログのサニタイズと機密情報の非出力
**Objective:** As a セキュリティ担当, I want 機密情報がログに出力されない, so that 情報漏えいリスクを最小化できる

#### Acceptance Criteria

- **4.1** When `/api/auth` または秘密情報を扱うエンドポイントへのリクエストが発生したとき, the Backend Service shall 設定 `LOG_REQUEST_BODY` に関わらずリクエストボディをログに出力しない
- **4.2** The Backend Service shall ログ出力時に機密情報（トークン、パスワード、シークレット値等）をマスクまたは除外する
- **4.3** If サニタイズ処理で例外が発生したとき, then the Backend Service shall ボディを破棄し最小限のメタデータのみを記録する
- **4.4** The Backend Service shall エラーレスポンスおよびログに秘密情報の平文を含めない

### Requirement 5: 暗号化キー管理の厳格化（Fail Fast）
**Objective:** As a 運用者, I want 暗号化キーが安全に供給され不備時に即時検知できる, so that 不完全な状態での運用を防げる

#### Acceptance Criteria
 
- **5.1** The Backend Service shall 暗号化キーを自動生成したりファイルへ保存したりしない
- **5.2** While Production プロファイルで動作するとき, the Backend Service shall 必須の暗号化キー環境変数が未設定の場合に起動を中止する
- **5.3** When 暗号化キーが提供されているとき, the Backend Service shall OAuth/GitHub トークン等の永続化対象資格情報を暗号化して保存する
- **5.4** The Backend Service shall 暗号化キーや復号に必要な値をログへ出力しない

### Requirement 6: SSRF 対策（カタログ取得 URL 検証）
**Objective:** As a セキュリティ担当, I want バックエンドが内部ネットワークへアクセスしない, so that SSRF による情報漏えいを防げる

#### Acceptance Criteria

- **6.1** When カタログ取得先 URL が設定または更新されるとき, the Backend Service shall スキーム/ホスト/ポートを検証し、許可されない URL を拒否する
- **6.2** If URL がループバック、リンクローカル、プライベート IP、メタデータ系アドレス等へ解決されるとき, then the Backend Service shall 当該アクセスをブロックする
- **6.3** When URL 検証で拒否されたとき, the Backend Service shall 拒否理由と修正手順を返す
- **6.4** The Backend Service shall SSRF 対策により内部ネットワーク資源への HTTP 要求を送信しない

### Requirement 7: Config と Secrets の分離
**Objective:** As a 開発者, I want 設定と機密情報の境界が明確で意図せず永続化されない, so that 誤保存による漏えいを防げる

#### Acceptance Criteria
 
- **7.1** The Backend Service shall 永続化される設定（Config）と揮発すべき機密情報（Secrets）を異なるモデル/API として扱う
- **7.2** When 設定を永続化するとき, the Backend Service shall Secrets を除外し、平文で保存しない
- **7.3** If Secrets を含む入力が提供されたとき, then the Backend Service shall Secrets を Config 永続化経路に流さず承認された保管経路に限定する
- **7.4** The Backend Service shall Secrets が意図せず DB に残らないことを検証可能にする

### Requirement 8: DevContainer による統合開発環境とテストポリシー
**Objective:** As a 開発者, I want 環境差異なく統合環境で開発・テストできる, so that チーム開発の再現性を高められる

#### Acceptance Criteria

- **8.1** The System shall リポジトリルートに `.devcontainer/` を含み、Backend/Worker/Frontend/Redis が連携して起動できる
- **8.2** When 開発者が VS Code で "Reopen in Container" を実行したとき, the Development Environment shall フロント（既定 3000）とバックエンド（既定 8000）へアクセス可能な状態で起動する
- **8.3** The System shall 自動テスト（Unit/Integration）を DevContainer 環境内で実行可能にする
- **8.4** The System shall テストは DevContainer 内で実行する方針と、`docker compose exec` または `devcontainer exec` を用いた実行例を開発者向けに提示する

### Requirement 9: 後方互換性（API コントラクト維持）
**Objective:** As a 利用者, I want リファクタリング後も既存 UI が継続して利用できる, so that 移行コストなく利用を継続できる

#### Acceptance Criteria
 
- **9.1** The Backend Service shall 既存フロントエンドが利用する主要 API のエンドポイント、HTTP ステータス、レスポンス構造を後方互換に維持する
- **9.2** If 互換性を破る変更が必要なとき, then the Backend Service shall 明示的なバージョニングまたは移行手順を提供する
- **9.3** The System shall リファクタリング後も主要機能（認証、カタログ取得、コンテナ操作、インスペクション）が継続して利用できる

