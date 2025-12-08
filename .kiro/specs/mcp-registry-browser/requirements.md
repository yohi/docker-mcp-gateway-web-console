# Requirements Document

## Project Description (Input)
カタログをhttps://github.com/docker/mcp-registryからリスト化して数回のクリックでインストールできるように簡略化したい

## Requirements

### Requirement 1: カタログデータの取得 (Catalog Data Retrieval)
**Objective:** As a Developer, I want to fetch the latest list of MCP servers from the official Docker registry, so that I can explore available tools.

#### Acceptance Criteria
1. The [Backend Service] shall [GitHubのdocker/mcp-registry（または指定されたURL）からMCPサーバーのメタデータリストを取得する]
2. If [外部レジストリへの接続が失敗した], then the [Backend Service] shall [エラーログを記録し、フロントエンドにエラー状態を通知する]
3. The [Backend Service] shall [取得したデータをフロントエンドが利用しやすい形式（JSON等）で提供する]

### Requirement 2: カタログの閲覧 (Catalog Browsing)
**Objective:** As a User, I want to view a formatted list of available MCP servers, so that I can choose which ones to install.

#### Acceptance Criteria
1. When [ユーザーがカタログページにアクセスした], the [Frontend Application] shall [サーバーリストのローディング状態を表示する]
2. The [Frontend Application] shall [各MCPサーバーの名前、説明、およびベンダー情報をカードまたはリスト形式で表示する]
3. Where [サーバーが既にローカル環境にインストールされている], the [Frontend Application] shall [「インストール済み」ステータスを該当アイテムに表示し、重複インストールを警告または防止する] (Ref: Product.md - Core Capabilities)

### Requirement 3: 簡易インストールフロー (Simplified Installation Flow)
**Objective:** As a User, I want to install an MCP server with minimal configuration, so that I can quickly start using it without complex CLI commands.

#### Acceptance Criteria
1. When [ユーザーがカタログから「インストール」を選択した], the [Frontend Application] shall [必要な環境変数やBitwarden参照設定を入力するための設定モーダルを表示する] (Ref: Tech.md - Secure Secret Management)
2. When [ユーザーが設定を確認しインストールを実行した], the [Backend Service] shall [Dockerイメージのプルとコンテナの作成・起動をバックグラウンドで開始する]
3. While [インストールが進行中である], the [Frontend Application] shall [進行状況（スピナーやプログレスバー）を表示し、操作をブロックまたは制限する]
4. If [コンテナの起動に失敗した], then the [Backend Service] shall [エラー詳細を返し、Frontend Applicationはユーザーに解決策またはエラーメッセージを表示する]
