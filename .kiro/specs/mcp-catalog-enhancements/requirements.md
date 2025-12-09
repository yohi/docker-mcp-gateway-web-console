# Requirements Document

## Introduction
本機能では、MCP Catalog の利用を拡張し、OAuth が必要なサーバー接続、動的なサーバー追加・実行、イメージ署名検証、外部/E2B ゲートウェイ接続を安全かつ一貫した UI/バックエンド体験として提供する。これにより、開発者は秘密情報を安全に扱いつつ、カタログからの導入・検証をスムーズに行える。

## Requirements

### Requirement 1: OAuth 認可フロー管理
**Objective:** 認可が必要な MCP サーバーを安全に接続したいオペレータとして、UI から OAuth フローを完結させ、トークンを安全に保管したい。

#### Acceptance Criteria
1. WHEN ユーザーが対象 MCP サーバーの OAuth 接続開始を要求する THEN バックエンド SHALL 乱数 state と PKCE コードを生成し認可 URL を返却する。
2. IF OAuth コールバックで state が一致しない THEN バックエンド SHALL 401 を返却し再認可手順を案内する。
3. WHEN アクセストークン取得が成功する THEN バックエンド SHALL トークンと期限を Bitwarden または暗号化ストレージに保存し格納キーを記録する。
4. WHERE トークン期限が 24 時間未満のとき THEN バックエンド SHALL ステータス API で「要再認可」ステータスを返却する。
5. WHEN ユーザーがトークン取り消しを要求する THEN バックエンド SHALL 保存済みトークンを削除しステータスを「未接続」に更新する。

### Requirement 2: Dynamic MCP サーバー管理
**Objective:** 会話中に MCP サーバーを探索・追加・設定変更・実行したいオペレータとして、セッション単位で動的にサーバーを管理したい。

#### Acceptance Criteria
1. WHEN ユーザーが検索条件を送信する THEN バックエンド SHALL カタログから名前・説明・必要シークレットを含む結果リストを返却する。
2. WHEN ユーザーがサーバー追加を要求する THEN バックエンド SHALL セッション固有のゲートウェイプロセスに対象サーバーを追加し設定を保持する。
3. IF ユーザーが設定変更を送信する THEN バックエンド SHALL 変更後の設定をセッションストアに保存し結果を返却する。
4. WHEN ユーザーが mcp-exec を要求する THEN バックエンド SHALL 対象ツールを実行し出力・終了コード・タイムスタンプを返却する。
5. WHEN ユーザーがサーバー削除またはセッション終了を行う THEN バックエンド SHALL 該当サーバーのプロセスと一時ファイルを停止・削除する。

### Requirement 3: MCP イメージ署名検証
**Objective:** 署名付きイメージのみを許可したいセキュリティ担当として、カタログ導入時に署名検証を必須化し、失敗時のハンドリングを明確にしたい。

#### Acceptance Criteria
1. IF verify_signatures が有効 THEN バックエンド SHALL `docker mcp gateway run` 実行時に署名検証オプションを必須で付与する。
2. WHEN 署名検証が失敗する THEN バックエンド SHALL 詳細理由と再試行手順を含むエラーを返却しデプロイを中断する。
3. WHERE UI で署名検証トグルを無効化したとき THEN フロントエンド SHALL 保存前にリスク警告ダイアログを表示する。
4. WHILE verify_signatures が有効 THE バックエンド SHALL 検証ログから秘密情報を除外し成功/失敗の要約のみ記録する。

### Requirement 4: 外部/E2B ゲートウェイ接続
**Objective:** E2B サンドボックスなど外部ゲートウェイを利用したいユーザーとして、URL/トークンを安全に登録し接続性を検証したい。

#### Acceptance Criteria
1. WHEN ユーザーが外部ゲートウェイの URL とトークンを保存する THEN バックエンド SHALL URL スキーマ検証と許可リストチェックを実施し安全に保存する。
2. WHEN 接続テストを実行する THEN バックエンド SHALL `/healthcheck` を呼び応答ステータスとレイテンシを返却する。
3. IF 接続テストが成功する THEN フロントエンド SHALL 「接続成功」ステータスを表示し外部モードを有効化する。
4. IF 接続テストが失敗する THEN フロントエンド SHALL エラー理由を表示し外部モードを無効化のまま保持する。
