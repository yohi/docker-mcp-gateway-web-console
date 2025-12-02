# 要件定義書

## はじめに

Docker MCP Gateway Web Consoleは、DockerベースのMCPサーバー群を統合管理するためのWebアプリケーションです。本システムは、Bitwarden連携による安全な認証と機密情報管理、Catalogからの容易なMCPサーバー導入、そして詳細な稼働監視・操作機能を提供します。セキュリティと効率性を重視する個人開発者を対象とし、APIキーなどの機密情報を設定ファイルにハードコードすることなく、Bitwarden参照のみで完結させることを目指します。

## 用語集

- **System**: Docker MCP Gateway Web Console
- **User**: 本システムを利用する個人開発者
- **Bitwarden**: パスワード管理サービス。ユーザーの機密情報を安全に保管する
- **Vault**: Bitwardenにおける、ユーザーの機密情報を格納する領域
- **MCP Server**: Model Context Protocol サーバー。Dockerコンテナとして実行される
- **Catalog**: 利用可能なMCPサーバーの情報を含むリポジトリ（JSON/YAML形式）
- **Secret**: APIキー、パスワードなどの機密情報
- **Container**: Dockerコンテナ。MCPサーバーの実行環境
- **Gateway Config**: MCPサーバー群を統合管理するための親設定ファイル
- **Session**: ユーザーがSystemにログインしてから、ログアウトまたはタイムアウトするまでの期間
- **Bitwarden Reference Notation**: Bitwardenのアイテムを参照する記法（例: `{{ bw:item-id:field }}`）
- **MCP Inspector**: 起動中のMCPサーバーの機能（Tools、Resources、Prompts）を解析・表示する機能

## 要件

### 要件1: Bitwarden認証

**ユーザーストーリー:** 個人開発者として、Bitwardenアカウントを使用してWebコンソールにログインしたい。これにより、機密情報を安全に管理できる。

#### 受入基準

1. WHEN ユーザーがBitwarden APIキーまたはマスターパスワードとメールアドレスを入力してログインボタンをクリックする THEN THE System SHALL ユーザー認証を実行し、成功時にSessionを確立する

2. WHEN 認証が成功する THEN THE System SHALL Bitwarden Vaultへのアクセス権を取得し、バックエンドで利用可能な状態にする

3. WHEN 認証が失敗する THEN THE System SHALL エラーメッセージを表示し、Sessionを確立しない

4. WHEN Sessionが一定時間（30分）非アクティブである THEN THE System SHALL 自動的にSessionを終了し、Vaultへのアクセス権を破棄する

5. WHEN ユーザーがログアウトボタンをクリックする THEN THE System SHALL 即座にSessionを終了し、Vaultへのアクセス権を破棄する

### 要件2: 機密情報の安全な注入

**ユーザーストーリー:** 個人開発者として、環境変数にAPIキーを直接入力せず、Bitwardenから参照したい。これにより、機密情報の漏洩リスクを最小化できる。

#### 受入基準

1. WHEN ユーザーがコンテナ起動設定画面で環境変数の値フィールドにBitwarden Reference Notationを入力する THEN THE System SHALL その記法を受け入れ、設定として保存する

2. WHEN コンテナ起動時にBitwarden Reference Notationを含む環境変数が存在する THEN THE System SHALL バックエンドでBitwarden Vaultから対応する値を取得し、環境変数に注入する

3. WHEN Bitwarden Vaultから値の取得に失敗する THEN THE System SHALL コンテナの起動を中止し、エラーメッセージをユーザーに表示する

4. WHEN 取得したSecretをメモリ上で処理する THEN THE System SHALL その値をディスク上のログファイルまたは設定ファイルに書き出さない

5. WHEN Gateway Configの編集画面で設定値を入力する THEN THE System SHALL Bitwarden Reference Notationの使用を許可する

### 要件3: Catalogからのサーバー導入

**ユーザーストーリー:** 個人開発者として、CatalogからMCPサーバーを簡単に選択して起動したい。これにより、手動設定の手間を削減できる。

#### 受入基準

1. WHEN ユーザーがCatalog画面を開く THEN THE System SHALL 指定されたCatalogソースURLから利用可能なMCPサーバーのリストを取得し、表示する

2. WHEN Catalogデータの取得中である THEN THE System SHALL ローディングインジケーターを表示し、UIをブロックしない

3. WHEN ユーザーがCatalog上のMCPサーバーを選択し、Installボタンをクリックする THEN THE System SHALL 起動設定画面に遷移し、推奨設定をプレフィルする

4. WHEN Catalogリストを表示する THEN THE System SHALL 各アイテムの名前、説明、推奨Dockerイメージ、デフォルト環境変数を含める

5. WHEN Catalogソースへの接続に失敗する THEN THE System SHALL エラーメッセージを表示し、キャッシュされたデータがあれば表示する

### 要件4: コンテナのライフサイクル管理

**ユーザーストーリー:** 個人開発者として、MCPサーバーコンテナを起動、停止、再起動、削除したい。これにより、サーバーの状態を柔軟に制御できる。

#### 受入基準

1. WHEN ユーザーが起動設定を完了し、起動ボタンをクリックする THEN THE System SHALL 指定された設定でDockerコンテナを作成し、起動する

2. WHEN ユーザーが実行中のコンテナに対して停止ボタンをクリックする THEN THE System SHALL そのコンテナを停止し、ステータスを更新する

3. WHEN ユーザーが停止中のコンテナに対して再起動ボタンをクリックする THEN THE System SHALL そのコンテナを再起動し、ステータスを更新する

4. WHEN ユーザーがコンテナに対して削除ボタンをクリックする THEN THE System SHALL 確認ダイアログを表示し、承認後にコンテナを削除する

5. WHEN ユーザーがコンテナのログ閲覧ボタンをクリックする THEN THE System SHALL そのコンテナの標準出力と標準エラー出力をリアルタイムで表示する

### 要件5: Gateway設定の管理

**ユーザーストーリー:** 個人開発者として、Gateway Configをグラフィカルに編集したい。これにより、設定ファイルを直接編集する必要がなくなる。

#### 受入基準

1. WHEN ユーザーがGateway Config編集画面を開く THEN THE System SHALL 現在の設定内容を読み込み、フォーム形式で表示する

2. WHEN ユーザーが設定値を変更し、保存ボタンをクリックする THEN THE System SHALL 変更内容を検証し、有効であれば設定ファイルに書き込む

3. WHEN 設定値にBitwarden Reference Notationが含まれる THEN THE System SHALL その記法を有効な値として受け入れる

4. WHEN 設定値の検証に失敗する THEN THE System SHALL エラーメッセージを表示し、保存を実行しない

5. WHEN 設定ファイルの書き込みに失敗する THEN THE System SHALL エラーメッセージを表示し、ユーザーに再試行を促す

### 要件6: MCP Inspectorによる機能解析

**ユーザーストーリー:** 個人開発者として、起動中のMCPサーバーが提供する機能を確認したい。これにより、サーバーの動作を理解し、適切に利用できる。

#### 受入基準

1. WHEN ユーザーが実行中のコンテナに対してInspectボタンをクリックする THEN THE System SHALL そのMCPサーバーに接続し、利用可能なToolsのリストを取得して表示する

2. WHEN MCP Inspectorが機能情報を取得する THEN THE System SHALL Resourcesのリストを取得して表示する

3. WHEN MCP Inspectorが機能情報を取得する THEN THE System SHALL Promptsのリストを取得して表示する

4. WHEN MCPサーバーへの接続に失敗する THEN THE System SHALL エラーメッセージを表示し、接続状態を確認するよう促す

5. WHEN 各機能項目を表示する THEN THE System SHALL 名前、説明、パラメータ情報を含める

### 要件7: Secretのメモリ管理

**ユーザーストーリー:** 個人開発者として、Bitwardenへのアクセス頻度を抑えつつ、セキュリティを維持したい。これにより、パフォーマンスとセキュリティのバランスを取れる。

#### 受入基準

1. WHEN Bitwarden VaultからSecretを取得する THEN THE System SHALL その値をSession期間中、メモリ内にキャッシュする

2. WHEN Sessionが終了する THEN THE System SHALL メモリ内のキャッシュされたSecretをすべて破棄する

3. WHEN キャッシュされたSecretを使用する THEN THE System SHALL ディスクへの書き込みを一切行わない

4. WHEN 同じSecretが再度必要になる THEN THE System SHALL キャッシュが有効であればBitwardenへの再アクセスを行わない

5. WHEN キャッシュの有効期限が切れる THEN THE System SHALL 次回アクセス時にBitwardenから再取得する

### 要件8: Catalogの検索とフィルタリング

**ユーザーストーリー:** 個人開発者として、多数のMCPサーバーから目的のものを素早く見つけたい。これにより、導入作業を効率化できる。

#### 受入基準

1. WHEN ユーザーがCatalog画面で検索ボックスにキーワードを入力する THEN THE System SHALL 名前または説明にそのキーワードを含むアイテムのみを表示する

2. WHEN ユーザーがカテゴリフィルターを選択する THEN THE System SHALL 選択されたカテゴリに属するアイテムのみを表示する

3. WHEN 検索またはフィルタリングの結果が0件である THEN THE System SHALL 「該当するアイテムがありません」というメッセージを表示する

4. WHEN ユーザーが検索ボックスをクリアする THEN THE System SHALL すべてのアイテムを再表示する

5. WHEN 複数のフィルター条件が適用される THEN THE System SHALL すべての条件を満たすアイテムのみを表示する

### 要件9: コンテナステータスの監視

**ユーザーストーリー:** 個人開発者として、すべてのコンテナの現在の状態を一目で把握したい。これにより、問題を迅速に発見できる。

#### 受入基準

1. WHEN ユーザーがコンテナ一覧画面を表示する THEN THE System SHALL 各コンテナの現在のステータス（実行中、停止中、エラー）を表示する

2. WHEN コンテナのステータスが変化する THEN THE System SHALL 5秒以内に画面上の表示を更新する

3. WHEN コンテナがエラー状態である THEN THE System SHALL そのコンテナを視覚的に強調表示する

4. WHEN ユーザーがステータス表示をクリックする THEN THE System SHALL 詳細情報（起動時刻、リソース使用状況）を表示する

5. WHEN Dockerデーモンとの通信に失敗する THEN THE System SHALL エラーメッセージを表示し、再接続を試みる

### 要件10: エラーハンドリングとユーザーフィードバック

**ユーザーストーリー:** 個人開発者として、エラーが発生した際に原因と対処法を理解したい。これにより、問題を自己解決できる。

#### 受入基準

1. WHEN Systemで予期しないエラーが発生する THEN THE System SHALL ユーザーに分かりやすいエラーメッセージを表示する

2. WHEN エラーメッセージを表示する THEN THE System SHALL 可能な限り具体的な原因と推奨される対処法を含める

3. WHEN 長時間実行される操作を開始する THEN THE System SHALL 進行状況インジケーターを表示する

4. WHEN 操作が正常に完了する THEN THE System SHALL 成功メッセージを3秒間表示する

5. WHEN 致命的なエラーが発生する THEN THE System SHALL エラー詳細をバックエンドログに記録し、ユーザーには簡潔なメッセージを表示する
