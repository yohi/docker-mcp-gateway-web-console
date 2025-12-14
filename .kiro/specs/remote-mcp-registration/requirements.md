# Requirements Document

## Introduction
本仕様は、Docker MCP Gateway Web Console から「リモート MCP サーバー（SaaS API エンドポイント）」を発見・登録し、OAuth 2.0（PKCE）による認証とランタイム統合を行うための要件を定義する。

本書では、要件の主体（the [system]）として以下を用いる。
- **Web Console**: ブラウザ上の UI（ユーザー操作・状態表示）
- **Backend Service**: Web Console が利用するバックエンド API（認証、永続化、実行制御）
- **Gateway Runtime**: MCP クライアントとの通信およびリモート MCP サーバーとの中継・変換を担う実行系

## Project Description (Input)
Docker MCP Toolkit におけるリモート MCP サーバー統合機能の実装。本機能は、Docker MCP Gateway Web Console からリモート MCP サーバー（SaaS API エンドポイント）の登録、OAuth 2.0 認証、およびランタイム統合を実現する。

### 主要コンポーネント
1. **リモートサーバー登録** - カタログからリモート MCP サーバー定義を取得し、ローカル Gateway 構成に注入するメカニズム
2. **OAuth 認証フロー** - PKCE を用いたセキュアな OAuth 2.0 認可コードフロー（ローカルループバック方式）
3. **クレデンシャル管理** - OS ネイティブのセキュアストア（Keychain, Credential Manager 等）との統合
4. **プロトコル変換** - Stdio ↔ SSE/HTTP プロトコル変換を行う Gateway ロジック
5. **Web コンソール UI** - リモートサーバーの発見、有効化、認証状態管理を行うユーザーインターフェース

### 技術的背景
- MCP プロトコル: JSON-RPC 2.0 ベース、Stdio/SSE トランスポート対応
- 認証方式: OAuth 2.0 + PKCE（RFC 7636 準拠）
- セキュリティ: TLS 暗号化、OS ネイティブキーストア統合、カタログホワイトリスト方式

### 参照ドキュメント
- Docker MCP Toolkit リモートインストール機構.md
- リモートMCP登録製造ドキュメント作成.md

## Requirements

### Requirement 1: リモートMCPサーバーの発見と詳細表示
**Objective:** As a 利用者, I want リモートMCPサーバーをカタログから検索して詳細を確認できる, so that 安全に統合先を選択できる

#### Acceptance Criteria
1. When ユーザーがリモートMCPサーバーの一覧画面を開いたとき, the Web Console shall カタログ由来のリモートMCPサーバー一覧を表示する
2. When ユーザーが検索またはフィルタ条件を変更したとき, the Web Console shall 一覧表示を条件に基づいて更新する
3. When ユーザーがサーバーを選択したとき, the Web Console shall サーバー定義の詳細（名称、提供元、説明、接続先エンドポイント、認証要否、要求スコープ、想定トランスポート）を表示する
4. If カタログの取得に失敗したとき, then the Web Console shall 失敗理由と再試行手段を表示する
5. Where 以前に取得したカタログデータが利用可能なとき, the Web Console shall カタログ取得に失敗した場合でも最後に成功したデータを閲覧可能にする

### Requirement 2: リモートMCPサーバーの登録・有効化・削除
**Objective:** As a 利用者, I want 選択したリモートMCPサーバーをローカルGatewayに登録して管理できる, so that 必要な統合を継続的に利用できる

#### Acceptance Criteria
1. When ユーザーがサーバー登録を実行したとき, the Backend Service shall 選択されたサーバー定義をローカルGatewayの管理対象として保存する
2. When サーバー登録が完了したとき, the Web Console shall 登録済みサーバー一覧に当該サーバーを表示する
3. If 同一識別子または同一エンドポイントのサーバーが既に登録済みのとき, then the Backend Service shall 重複登録を拒否し、その理由を返す
4. When ユーザーが登録済みサーバーを無効化したとき, the Backend Service shall 当該サーバーへのランタイム統合を停止状態にする
5. When ユーザーが登録済みサーバーを削除したとき, the Backend Service shall 当該サーバーの設定情報を削除する
6. While サーバーが削除されるまでの間, the Backend Service shall 当該サーバーに紐づく認証情報の削除可否と影響をユーザーに判断可能な形で提供する

### Requirement 3: OAuth 2.0（PKCE）認可フローの開始
**Objective:** As a 利用者, I want リモートMCPサーバーに対してOAuth 2.0で安全に認可を開始できる, so that 追加の資格情報入力なしに利用できる

#### Acceptance Criteria
1. When ユーザーが「認証/認可を開始」を選択したとき, the Web Console shall 対象サーバーのOAuth認可フロー開始操作を提供する
2. When OAuth 認可フローを開始するとき, the Backend Service shall OAuth 2.0 認可コードフロー（PKCE を含む）に必要なパラメータを生成する
3. When OAuth 認可フローを開始するとき, the Backend Service shall CSRF対策として state パラメータを生成し、検証可能な形で保持する
4. When 認可URLが生成されたとき, the Web Console shall ユーザーが認可ページへ遷移できる手段を提供する
5. If 対象サーバーがOAuthを要求しないとき, then the Web Console shall OAuth 認可フロー開始操作を要求しない状態で登録/有効化を進められるようにする

### Requirement 4: OAuth コールバック処理とトークン管理
**Objective:** As a 利用者, I want OAuth 認可結果を安全に取り込み、認証状態を維持できる, so that リモートMCPサーバーを継続利用できる

#### Acceptance Criteria
1. When OAuth コールバックを受信したとき, the Backend Service shall state の整合性を検証する
2. If state の検証に失敗したとき, then the Backend Service shall 認可結果を拒否し、認証失敗として扱う
3. When state の検証に成功したとき, the Backend Service shall 認可コードを用いてアクセストークンを取得する
4. If トークン取得に失敗したとき, then the Backend Service shall 失敗理由を返し、再試行可能な状態を維持する
5. When トークン取得が成功したとき, the Backend Service shall 対象サーバーの認証状態を「認証済み」として更新する
6. Where リフレッシュトークンが提供されるとき, the Backend Service shall アクセストークンが失効した場合に再取得できるようにする
7. If ユーザーが認証解除を実行したとき, then the Backend Service shall 当該サーバーに紐づく保存済みトークンを利用不能にする

### Requirement 5: クレデンシャルの安全な保管と削除
**Objective:** As a 利用者, I want 認証情報が安全に保管・削除される, so that 秘密情報をディスクに残さずに運用できる

#### Acceptance Criteria
1. The Backend Service shall 認証情報（アクセストークン等）を平文のまま永続化しない
2. When 認証情報を永続化するとき, the Backend Service shall OS ネイティブのセキュアストアに保管する
3. If OS ネイティブのセキュアストアが利用できないとき, then the Backend Service shall 暗号化された形でのみ永続化する
4. When ユーザーが認証情報の削除を要求したとき, the Backend Service shall 当該認証情報を永続ストアから削除する
5. While 認証情報が存在する間, the Web Console shall 当該情報の有無と紐づくサーバーをユーザーが確認できるように表示する
6. The Backend Service shall ログおよびエラー応答に認証情報を含めない

### Requirement 6: ランタイム統合とプロトコル変換
**Objective:** As a 利用者, I want 登録済みリモートMCPサーバーをGateway経由で利用できる, so that ローカルのMCP利用体験を維持したままSaaSと統合できる

#### Acceptance Criteria
1. When リモートMCPサーバーが有効化され、必要な認証が満たされているとき, the Gateway Runtime shall 当該サーバーへのMCPリクエストを中継できるようにする
2. When MCP クライアントが Stdio トランスポートで接続しているとき, the Gateway Runtime shall リモート側の SSE/HTTP トランスポートと相互運用できるようにプロトコル変換する
3. The Gateway Runtime shall MCP の JSON-RPC 2.0 メッセージ構造を保持したままリクエスト/レスポンスを中継する
4. If リモートサーバーが到達不能または応答不能のとき, then the Gateway Runtime shall 失敗をMCPクライアントへ明確なエラーとして返す
5. When ユーザーが接続テストを実行したとき, the Backend Service shall 当該サーバーへの到達性と認証状態を確認し、結果を返す

### Requirement 7: Webコンソールでの状態管理（認証・接続・エラー）
**Objective:** As a 利用者, I want 各リモートMCPサーバーの状態を一目で把握し、必要な操作を行える, so that 迷わずに運用できる

#### Acceptance Criteria
1. The Web Console shall サーバーごとに状態（未登録/登録済み/要認証/認証済み/無効/エラー）を表示する
2. When 認証状態が変化したとき, the Web Console shall 表示状態を更新する
3. When 接続テストが失敗したとき, the Web Console shall 失敗理由と推奨アクション（再試行、再認証、無効化等）を表示する
4. While OAuth 認可フローが進行中のとき, the Web Console shall 進行中であることと完了/失敗の結果をユーザーに提示する
5. When ユーザーが再認証を選択したとき, the Web Console shall 当該サーバーのOAuth認可フロー再実行を開始できるようにする

### Requirement 8: セキュリティ制約（TLS・許可リスト・安全な取り扱い）
**Objective:** As a 管理者, I want リモートMCP統合がセキュリティ方針に従って制約される, so that 不正な外部接続や情報漏えいを防げる

#### Acceptance Criteria
1. The Backend Service shall リモートMCPサーバーへの通信にTLSを要求する
2. If リモートMCPサーバー定義のエンドポイントがTLSを満たさないとき, then the Backend Service shall 当該サーバーの登録または有効化を拒否する
3. The Backend Service shall カタログおよびOAuth関連エンドポイントに対して許可リストに基づく検証を行う
4. If 許可リスト外のドメインが指定されたとき, then the Backend Service shall 当該アクセスを拒否し、その理由を返す
5. The Backend Service shall OAuth 認可フローにおいて state によるリクエスト整合性検証を必須とする
6. The Web Console shall 認証情報や機微情報が画面表示・ログ・エラー文に露出しないように扱う

### Requirement 9: 監査・メトリクス（追跡可能性）
**Objective:** As a 管理者, I want 重要操作が監査可能に記録される, so that 事後追跡と運用判断ができる

#### Acceptance Criteria
1. When ユーザーがサーバーを登録したとき, the Backend Service shall 監査可能なイベントとして記録する
2. When ユーザーがサーバーを有効化または無効化したとき, the Backend Service shall 監査可能なイベントとして記録する
3. When OAuth 認可フローが開始/成功/失敗したとき, the Backend Service shall 監査可能なイベントとして記録する
4. When 許可リスト検証によりアクセスが拒否されたとき, the Backend Service shall 監査可能なイベントとして記録する
5. The Web Console shall 直近の操作結果（成功/失敗）をユーザーが確認できる形で提示する

### Requirement 10: 失敗時の振る舞いと復旧
**Objective:** As a 利用者, I want 失敗時でも原因を理解して復旧できる, so that 作業が中断しない

#### Acceptance Criteria
1. If ネットワークエラーが発生したとき, then the Backend Service shall ユーザーが識別可能なエラー情報を返す
2. If 外部サービスが一時的に不安定なとき, then the Web Console shall 再試行手段を提供する
3. While 認証が失効または不足している間, the Gateway Runtime shall 当該サーバーへのリクエストを成功扱いにしない
4. When ユーザーが無効化操作を行ったとき, the Gateway Runtime shall 当該サーバーへの中継を停止し、他サーバーの利用に影響を与えない
5. The Backend Service shall 重大な失敗が発生しても登録情報の整合性を保つ
