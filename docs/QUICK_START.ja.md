[English](QUICK_START.md)

# クイックスタートガイド

Docker MCP Gateway Consoleを5分で立ち上げて実行しましょう！

## 前提条件チェックリスト

開始する前に、以下を確認してください：

- [ ] Dockerがインストールされ、実行されていること
- [ ] Node.js 18+ がインストールされていること
- [ ] Python 3.11+ がインストールされていること
- [ ] Bitwarden CLI がインストールされていること
- [ ] シークレットを含むアイテムが少なくとも1つあるBitwardenアカウント

## ステップ 1: Bitwarden CLIのインストール (2分)

### macOS
```bash
brew install bitwarden-cli
```

### Linux
```bash
npm install -g @bitwarden/cli
```

### インストールの確認
```bash
bw --version
# 出力例: 2023.x.x またはそれ以降
```

## ステップ 2: クローンとセットアップ (2分)

```bash
# リポジトリのクローン
git clone <repository-url>
cd docker-mcp-gateway-console

# 環境ファイルのコピー
cp frontend/.env.local.example frontend/.env.local
cp backend/.env.example backend/.env

# Docker Composeで起動
docker-compose up -d
```

## ステップ 3: アプリケーションへのアクセス (30秒)

ブラウザを開き、以下にアクセスします：
- **フロントエンド**: http://localhost:3000
- **バックエンドAPI**: http://localhost:8000/docs

## ステップ 4: Bitwardenでログイン (1分)

### オプション A: APIキーの使用（推奨）

1. Bitwarden Web保管庫 → 設定 → セキュリティ → キー へ移動
2. 「APIキーを表示」をクリック
3. `client_id` と `client_secret` をコピー
4. コンソールのログインページで：
   - Bitwardenのメールアドレスを入力
   - 「API Key」メソッドを選択
   - 認証情報を貼り付け
   - 「Login」をクリック

### オプション B: マスターパスワードの使用

1. コンソールのログインページで：
   - Bitwardenのメールアドレスを入力
   - 「Master Password」メソッドを選択
   - マスターパスワードを入力
   - 「Login」をクリック

## ステップ 5: 最初のMCPサーバーのデプロイ (2分)

### Bitwardenでシークレットを準備

1. Bitwarden Web保管庫を開く
2. 新しいアイテムを作成（例：「GitHub Token」）
3. GitHubパーソナルアクセストークンを含む「token」という名前のカスタムフィールドを追加
4. URLからアイテムIDをメモする

### カタログからインストール

1. ナビゲーションの「Catalog」をクリック
2. 「GitHub」（または希望するサーバー）を検索
3. 「Install」をクリック
4. 環境変数を設定：
   - `GITHUB_TOKEN` に `{{ bw:YOUR-ITEM-ID:token }}` と入力
   - `YOUR-ITEM-ID` を実際のBitwardenアイテムIDに置き換える
5. 「Start Container」をクリック

> 補足: 設定画面「GitHubトークン設定」からBitwarden検索→保存を行うと、トークンが暗号化保存されカタログ取得時に自動利用されます（値は表示されません）。

### 実行確認

1. 「Dashboard」へ移動
2. コンテナのステータスが「Running」になっていることを確認
3. 「Logs」をクリックしてコンテナ出力を確認
4. 「Inspect」をクリックして利用可能なツール、リソース、プロンプトを確認

## 次は何をする？

### 機能の探索

- **Dashboard**: すべての実行中コンテナを監視
- **Catalog**: さらに多くのMCPサーバーを閲覧・インストール
- **Config Editor**: ゲートウェイ設定を管理
- **Inspector**: MCPサーバーの機能を分析

### サーバーの追加

ステップ5を繰り返して、カタログからさらにMCPサーバーを追加します。

### カスタム設定の作成

1. Dashboardの「New Container」をクリック
2. 任意のDockerイメージを入力
3. Bitwarden参照を使用して環境変数を設定
4. コンテナを起動

## 初回によくある問題

### "Bitwarden CLI not found"

**解決策:**
```bash
# インストールの確認
which bw

# 見つからない場合、インストール
npm install -g @bitwarden/cli

# バックエンド .env を更新
echo "BITWARDEN_CLI_PATH=$(which bw)" >> backend/.env
```

### "Cannot connect to Docker daemon"

**解決策:**
```bash
# Dockerが実行中か確認
docker ps

# Linuxの場合、ユーザーをdockerグループに追加
sudo usermod -aG docker $USER
# その後、ログアウトして再ログイン
```

### "Invalid Bitwarden reference"

**解決策:**
- Bitwarden Web保管庫URLのアイテムIDを再確認
- フィールド名が正確に一致しているか確認（大文字小文字を区別）
- 形式が正しいか確認: `{{ bw:item-id:field }}`

### "Session expired"

**解決策:**
- セッションは30分間の非アクティブ状態で期限切れになります
- 単に再度ログインしてください

## クイックリファレンス

### Bitwarden参照形式

```
{{ bw:item-id:field }}
```

**例:**
- `{{ bw:abc123:password }}` - パスワードフィールド
- `{{ bw:def456:username }}` - ユーザー名フィールド
- `{{ bw:ghi789:api_key }}` - "api_key" という名前のカスタムフィールド

### アイテムIDの確認

1. Bitwarden Web保管庫を開く
2. アイテムをクリック
3. URLを確認: `...?itemId=YOUR-ITEM-ID`

### 便利なコマンド

```bash
# ログを表示
docker-compose logs -f

# サービスの再起動
docker-compose restart

# サービスの停止
docker-compose down

# 更新と再起動
git pull
docker-compose up -d --build
```

## ヘルプを得る

- **ドキュメント**: [メインREADME](../README.ja.md)を確認
- **FAQ**: [FAQ.ja.md](FAQ.ja.md)を参照
- **Issues**: GitHubでバグを報告
- **ログ**: アプリケーションログのエラーを確認

## 次のステップ

1. **完全なドキュメントを読む**: [README.ja.md](../README.ja.md)
2. **環境変数を調べる**: [ENVIRONMENT_VARIABLES.ja.md](ENVIRONMENT_VARIABLES.ja.md)
3. **デプロイについて学ぶ**: [DEPLOYMENT.ja.md](DEPLOYMENT.ja.md)
4. **独自のカタログを作成する**: [CATALOG_SCHEMA.ja.md](CATALOG_SCHEMA.ja.md)

## 成功へのヒント

1. **シンプルに始める**: 1つか2つのサーバーから始める
2. **APIキーを使用する**: マスターパスワード認証よりも簡単
3. **シークレットを整理する**: Bitwarden保管庫を整理しておく
4. **ログを確認する**: 動作しない場合は常にコンテナログを確認する
5. **ドキュメントを読む**: 各MCPサーバーには特定の要件がある場合があります

## ワークフロー例

セットアップ後の典型的なワークフローは以下の通りです：

1. **朝**: コンソールにログイン
2. **閲覧**: カタログで新しいサーバーをチェック
3. **インストール**: 必要なサーバーを追加（例：Slack連携）
4. **設定**: Bitwarden参照を使用して環境変数を設定
5. **デプロイ**: コンテナを起動
6. **監視**: ログとステータスを確認
7. **使用**: MCPサーバーがAIツールで利用可能になります
8. **夕方**: コンテナは実行し続け、セッションは自動的に期限切れになります

## おめでとうございます！ 🎉

これで、安全なシークレット管理を備えたMCPサーバーを管理する準備が整いました！

より高度な使用方法については、完全なドキュメントをご覧ください。
