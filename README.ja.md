[English](README.md)

# Docker MCP Gateway Console

DockerベースのMCP（Model Context Protocol）サーバーを管理するための包括的なWebコンソールであり、安全なシークレット管理のためにBitwardenと統合されています。このアプリケーションは、APIキーや機密情報を安全に保ちながら、MCPサーバーのデプロイ、設定、監視を行うためのユーザーフレンドリーなインターフェースを提供します。

## 機能

- 🔐 **Bitwarden認証**: Bitwarden APIキーまたはマスターパスワードを使用した安全なログイン
- 🐳 **コンテナライフサイクル管理**: MCPサーバーコンテナの起動、停止、再起動、削除
- 📦 **カタログブラウザ**: キュレーションされたカタログからのMCPサーバーの閲覧とインストール
- 🔍 **MCPインスペクター**: サーバー機能（ツール、リソース、プロンプト）の分析
- ⚙️ **ゲートウェイ設定エディタ**: MCPゲートウェイ設定のためのビジュアルエディタ
- 🔒 **安全なシークレット注入**: ディスクに保存せずにBitwardenシークレットを参照
- 📊 **リアルタイム監視**: コンテナステータスの更新とログストリーミング
- 🎨 **モダンUI**: Tailwind CSSを使用したレスポンシブデザイン

## アーキテクチャ

- **フロントエンド**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS
- **バックエンド**: Python 3.11+, FastAPI, Docker SDK
- **シークレット管理**: メモリ内キャッシュを備えたBitwarden CLI統合
- **コンテナ管理**: リアルタイムログストリーミングを備えたDocker Engine
- **通信**: REST API + ログストリーミング用WebSocket

## 前提条件

開始する前に、以下がインストールされていることを確認してください：

- **Node.js 18+**: [ダウンロード](https://nodejs.org/)
- **Python 3.11+**: [ダウンロード](https://www.python.org/downloads/)
- **Docker Engine 20.10+**: [Dockerのインストール](https://docs.docker.com/engine/install/)
- **Bitwarden CLI 2023.x+**: [Bitwarden CLIのインストール](https://bitwarden.com/help/cli/)
- **Docker Compose**: 通常Docker Desktopに含まれています
- **Bitwardenアカウント**: シークレットを含む保管庫（ボールト）を持つBitwardenアカウントが必要です

### Bitwarden CLIのインストール

```bash
# macOS (Homebrewを使用)
brew install bitwarden-cli

# Linux (npmを使用)
npm install -g @bitwarden/cli

# インストールの確認
bw --version
```

## クイックスタート

**プロジェクトは初めてですか？** 5分でセットアップできる[クイックスタートガイド](docs/QUICK_START.ja.md)をご覧ください！

### オプション1: Docker Composeでの開発（推奨）

1. **リポジトリのクローン:**
```bash
git clone <repository-url>
cd docker-mcp-gateway-console
```

2. **環境変数のセットアップ:**
```bash
# フロントエンド
cp frontend/.env.local.example frontend/.env.local
# 必要に応じて frontend/.env.local を編集

# バックエンド
cp backend/.env.example backend/.env
# 必要に応じて backend/.env を編集
```

3. **開発環境の起動:**
```bash
docker-compose up
```

4. **アプリケーションへのアクセス:**
   - フロントエンド: http://localhost:3000
   - バックエンドAPI: http://localhost:8000
   - APIドキュメント: http://localhost:8000/docs

5. **Bitwardenでログイン:**
   - http://localhost:3000 を開く
   - BitwardenのメールアドレスとAPIキー（またはマスターパスワード）を入力
   - MCPサーバーの管理を開始！

### オプション2: ローカル開発（Docker Composeなし）

このオプションは、サービスを個別に実行したい開発時に便利です。

### E2Eテストの実行

完全なE2Eテストスイートを実行するには：

```bash
# 提供されているスクリプトを使用
./scripts/run-e2e-tests.sh

# またはDocker Composeで手動実行
docker-compose -f docker-compose.test.yml up -d frontend backend
cd frontend
npm run test:e2e
```

詳細なテストドキュメントについては、[frontend/e2e/README.md](frontend/e2e/README.md)を参照してください。

#### バックエンドのセットアップ

```bash
cd backend

# 仮想環境の作成
python -m venv venv

# 仮想環境のアクティベート
source venv/bin/activate  # Windowsの場合: venv\Scripts\activate

# 依存関係のインストール
pip install -r requirements.txt

# 環境変数のセットアップ
cp .env.example .env
# 設定に合わせて .env を編集

# バックエンドの実行
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

バックエンドは http://localhost:8000 で利用可能になります

#### フロントエンドのセットアップ

```bash
cd frontend

# 依存関係のインストール
npm install

# 環境変数のセットアップ
cp .env.local.example .env.local
# バックエンドURLに合わせて .env.local を編集

# フロントエンドの実行
npm run dev
```

フロントエンドは http://localhost:3000 で利用可能になります

## プロジェクト構造

```
docker-mcp-gateway-console/
├── frontend/                 # Next.js フロントエンドアプリケーション
│   ├── app/                 # Next.js App Router ページ
│   ├── components/          # React コンポーネント
│   ├── lib/                 # ユーティリティ関数
│   └── public/              # 静的アセット
├── backend/                 # FastAPI バックエンドアプリケーション
│   ├── app/
│   │   ├── api/            # API ルートハンドラ
│   │   ├── models/         # Pydantic モデル
│   │   ├── services/       # ビジネスロジックサービス
│   │   ├── config.py       # 設定管理
│   │   └── main.py         # FastAPI アプリケーション
│   └── tests/              # バックエンドテスト
├── docker-compose.yml       # 開発環境
└── README.md
```

## 利用ガイド

### 初回セットアップ

1. **Bitwarden保管庫の準備:**
   - BitwardenでAPIキーとシークレット用のアイテムを作成
   - アイテムIDをメモする（Bitwarden Web保管庫のURLで確認可能）

2. **コンソールへのログイン:**
   - http://localhost:3000 に移動
   - Bitwardenのメールアドレスを入力
   - 認証方法を選択:
     - **APIキー**（推奨）: Bitwarden設定から生成
     - **マスターパスワード**: Bitwardenのマスターパスワード

3. **カタログの閲覧:**
   - カタログページへ移動
   - キーワードまたはカテゴリでMCPサーバーを検索
   - デプロイしたいサーバーの「インストール」をクリック

4. **設定と起動:**
   - コンテナ設定を入力
   - シークレットにはBitwarden参照記法を使用: `{{ bw:item-id:field }}`
   - 例: `{{ bw:abc123:password }}` はアイテム "abc123" の "password" フィールドを参照
   - 「コンテナを起動（Start Container）」をクリック

5. **監視と検査:**
   - ダッシュボードでコンテナのステータスを確認
   - 「ログ（Logs）」をクリックしてリアルタイム出力を確認
   - 「検査（Inspect）」をクリックしてMCPサーバーの機能（ツール、リソース、プロンプト）を表示

### Bitwarden参照記法

Bitwarden保管庫からシークレットを安全に参照するには：

**形式:** `{{ bw:item-id:field }}`

**例:**
- `{{ bw:a1b2c3d4:password }}` - パスワードフィールドを参照
- `{{ bw:e5f6g7h8:api_key }}` - "api_key" という名前のカスタムフィールドを参照
- `{{ bw:i9j0k1l2:username }}` - ユーザー名フィールドを参照

**アイテムIDの確認方法:**
1. Bitwarden Web保管庫を開く
2. アイテムをクリック
3. アイテムIDはURLに含まれています: `https://vault.bitwarden.com/#/vault?itemId=YOUR-ITEM-ID`

## 設定

詳細な設定オプションについては、[ENVIRONMENT_VARIABLES.ja.md](docs/ENVIRONMENT_VARIABLES.ja.md)を参照してください。

## テスト

### フロントエンド単体テスト

```bash
cd frontend
npm test
```

### フロントエンドE2Eテスト

```bash
cd frontend

# Playwrightブラウザのインストール（初回のみ）
npx playwright install

# E2Eテストの実行
npm run test:e2e

# UIモードでE2Eテストを実行
npm run test:e2e:ui

# ヘッドレスモード以外でE2Eテストを実行
npm run test:e2e:headed
```

詳細なE2Eテストドキュメントについては、[frontend/e2e/README.md](frontend/e2e/README.md)を参照してください。

### バックエンドテスト

```bash
cd backend
pytest
```

## デプロイ

本番環境へのデプロイ手順については、[DEPLOYMENT.ja.md](docs/DEPLOYMENT.ja.md)を参照してください。

## トラブルシューティング

### 一般的な問題

**"Bitwarden CLI not found"**
- Bitwarden CLIがインストールされているか確認: `bw --version`
- バックエンドの `.env` ファイル内の `BITWARDEN_CLI_PATH` を更新

**"Cannot connect to Docker daemon"**
- Dockerが実行されているか確認: `docker ps`
- バックエンドの `.env` ファイル内の `DOCKER_HOST` を確認
- Linuxの場合、ユーザーが `docker` グループに属しているか確認

**"Session timeout"**
- セッションは30分間の非アクティブ状態で期限切れになります
- 単に再度ログインして新しいセッションを作成してください

**"Container fails to start"**
- UIでコンテナログを確認
- Bitwarden参照が正しいか確認
- Dockerイメージが存在し、アクセス可能か確認

### ヘルプを得るには

- [FAQ](docs/FAQ.ja.md)を確認
- [要件定義](.kiro/specs/docker-mcp-gateway-console/requirements.md)を確認
- [設計ドキュメント](.kiro/specs/docker-mcp-gateway-console/design.md)を確認

## ドキュメント

### はじめに
- [クイックスタートガイド](docs/QUICK_START.ja.md) - 5分で開始
- [FAQ](docs/FAQ.ja.md) - よくある質問

### 設定とデプロイ
- [環境変数](docs/ENVIRONMENT_VARIABLES.ja.md) - 完全な設定リファレンス
- [デプロイガイド](docs/DEPLOYMENT.ja.md) - 本番環境デプロイ手順

### 開発
- [アーキテクチャドキュメント](docs/ARCHITECTURE.ja.md) - システムアーキテクチャと設計
- [貢献ガイド](CONTRIBUTING.ja.md) - プロジェクトへの貢献方法
- [APIドキュメント](http://localhost:8000/docs) - インタラクティブなAPIドキュメント（実行時）
- [E2Eテストガイド](frontend/e2e/README.md) - エンドツーエンドテストドキュメント

### カタログ
- [カタログスキーマ](docs/CATALOG_SCHEMA.ja.md) - 独自のカタログ作成方法
- [サンプルカタログ](docs/sample-catalog.json) - カタログファイルの例

### 仕様書
- [要件定義書](.kiro/specs/docker-mcp-gateway-console/requirements.md)
- [設計書](.kiro/specs/docker-mcp-gateway-console/design.md)
- [実装タスク](.kiro/specs/docker-mcp-gateway-console/tasks.md)

## 貢献

貢献は大歓迎です！プルリクエストを送信する前に、[貢献ガイド](CONTRIBUTING.ja.md)をお読みください。

### 貢献方法

1. リポジトリをフォーク
2. 機能ブランチを作成
3. 変更を行う
4. 新機能のテストを追加
5. すべてのテストが通過することを確認
6. プルリクエストを送信

詳細なガイドラインについては、[CONTRIBUTING.ja.md](CONTRIBUTING.ja.md)を参照してください。

## セキュリティ

- シークレットは決してディスクに書き込まれません
- すべてのシークレットはセッション中のみメモリに保存されます
- セッションは30分間の非アクティブ状態で自動的に期限切れになります
- 本番環境ではHTTPSを使用してください

## ライセンス

[ここにライセンスを追加]
