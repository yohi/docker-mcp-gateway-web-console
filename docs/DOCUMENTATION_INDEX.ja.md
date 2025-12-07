[English](DOCUMENTATION_INDEX.md)

# ドキュメントインデックス

Docker MCP Gateway Consoleプロジェクトの全ドキュメントの完全なインデックスです。

## クイックナビゲーション

### 🚀 はじめに
- **[クイックスタートガイド](QUICK_START.ja.md)** - 5分で開始
- **[README](../README.ja.md)** - プロジェクト概要と基本セットアップ
- **[FAQ](FAQ.ja.md)** - よくある質問とトラブルシューティング

### ⚙️ 設定
- **[環境変数](ENVIRONMENT_VARIABLES.ja.md)** - 完全な設定リファレンス
- **[カタログスキーマ](CATALOG_SCHEMA.ja.md)** - 独自のMCPサーバーカタログ作成方法
- **[サンプルカタログ](sample-catalog.json)** - 15のMCPサーバーを含むカタログ例

### 🚢 デプロイ
- **[デプロイメントガイド](DEPLOYMENT.ja.md)** - 本番環境デプロイ手順
  - Docker Composeデプロイ
  - 個別のサービスデプロイ
  - クラウドプラットフォームデプロイ (AWS, GCP, DigitalOcean)
  - セキュリティ強化
  - 監視とメンテナンス
  - バックアップと復旧

### 🏗️ アーキテクチャと開発
- **[アーキテクチャドキュメント](ARCHITECTURE.ja.md)** - システムアーキテクチャと設計上の決定
- **[貢献ガイド](../CONTRIBUTING.ja.md)** - プロジェクトへの貢献方法
- **[変更履歴](../CHANGELOG.ja.md)** - バージョン履歴とリリースノート

### 🧪 テスト
- **[E2Eテストガイド](../frontend/e2e/README.md)** - Playwrightを使用したE2Eテスト
- **[統合テスト](../INTEGRATION_TESTING.ja.md)** - 統合テストのセットアップ
- **[E2Eセットアップサマリー](../E2E_SETUP_SUMMARY.ja.md)** - E2Eテスト環境のセットアップ

### 📋 仕様書
- **[要件定義](../.kiro/specs/docker-mcp-gateway-console/requirements.md)** - 詳細な要件仕様
- **[設計書](../.kiro/specs/docker-mcp-gateway-console/design.md)** - システム設計と正当性プロパティ
- **[実装タスク](../.kiro/specs/docker-mcp-gateway-console/tasks.md)** - 開発タスクリスト

## 対象読者別ドキュメント

### エンドユーザー向け

1. [クイックスタートガイド](QUICK_START.ja.md)から始める
2. 一般的な質問については[FAQ](FAQ.ja.md)を読む
3. [環境変数](ENVIRONMENT_VARIABLES.ja.md)を使用して設定する
4. [デプロイメントガイド](DEPLOYMENT.ja.md)でデプロイする

### 開発者向け

1. プロジェクト概要について[README](../README.ja.md)を読む
2. [アーキテクチャドキュメント](ARCHITECTURE.ja.md)を確認する
3. [貢献ガイド](../CONTRIBUTING.ja.md)に従う
4. [要件定義](../.kiro/specs/docker-mcp-gateway-console/requirements.md)と[設計](../.kiro/specs/docker-mcp-gateway-console/design.md)を確認する

### カタログ作成者向け

1. [カタログスキーマ](CATALOG_SCHEMA.ja.md)を確認する
2. [サンプルカタログ](sample-catalog.json)を研究する
3. アプリケーションでカタログをテストする

### DevOpsエンジニア向け

1. [デプロイメントガイド](DEPLOYMENT.ja.md)を読む
2. [環境変数](ENVIRONMENT_VARIABLES.ja.md)を設定する
3. [アーキテクチャドキュメント](ARCHITECTURE.ja.md)を確認する
4. 監視とバックアップをセットアップする

## ドキュメント構造

```
docker-mcp-gateway-console/
├── README.md                    # メインプロジェクトドキュメント
├── CONTRIBUTING.md              # 貢献ガイドライン
├── CHANGELOG.md                 # バージョン履歴
├── .env.example                 # 本番環境テンプレート
├── docker-compose.prod.yml      # 本番用Docker Compose
│
├── docs/                        # ドキュメントディレクトリ
│   ├── DOCUMENTATION_INDEX.md   # このファイル
│   ├── QUICK_START.md          # 5分セットアップガイド
│   ├── FAQ.md                  # よくある質問
│   ├── ENVIRONMENT_VARIABLES.md # 設定リファレンス
│   ├── DEPLOYMENT.md           # 本番環境デプロイ
│   ├── ARCHITECTURE.md         # システムアーキテクチャ
│   ├── CATALOG_SCHEMA.md       # カタログ形式仕様
│   └── sample-catalog.json     # カタログ例
│
├── .kiro/specs/                # 公式仕様書
│   └── docker-mcp-gateway-console/
│       ├── requirements.md     # 要件仕様書
│       ├── design.md          # 設計書
│       └── tasks.md           # 実装タスク
│
├── frontend/
│   ├── Dockerfile             # 本番用フロントエンドDockerfile
│   └── e2e/
│       └── README.md          # E2Eテストガイド
│
└── backend/
    └── Dockerfile             # 本番用バックエンドDockerfile
```

## ドキュメント化された主な機能

### セキュリティ
- Bitwarden認証（APIキーとマスターパスワード）
- ディスク永続化なしの安全なシークレット注入
- 自動タイムアウト付きセッション管理
- メモリ内シークレットキャッシュ
- 本番環境向けのHTTPS設定

### コンテナ管理
- Dockerコンテナライフサイクル（作成、起動、停止、再起動、削除）
- WebSocket経由のリアルタイムログストリーミング
- コンテナステータス監視
- リソース設定

### MCP統合
- カタログ閲覧と検索
- カタログからのMCPサーバーインストール
- 機能分析用MCPインスペクター
- ゲートウェイ設定エディタ

### 開発
- Docker Compose開発環境
- 単体テスト（Jest, pytest）
- E2Eテスト（Playwright）
- コード品質ツール（ESLint, Black, Flake8）

## 外部リソース

### 技術
- [Next.js Documentation](https://nextjs.org/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Documentation](https://docs.docker.com/)
- [Bitwarden CLI](https://bitwarden.com/help/cli/)
- [MCP Protocol](https://modelcontextprotocol.io/)

### ツール
- [Playwright Testing](https://playwright.dev/)
- [Jest Testing](https://jestjs.io/)
- [pytest Documentation](https://docs.pytest.org/)

## ドキュメント標準

すべてのドキュメントは以下の標準に従います：

1. **Markdown形式**: 一貫性のためにすべてのドキュメントでMarkdownを使用
2. **明確な構造**: 目次付きの論理的な構成
3. **コード例**: すべての機能に対する実用的な例
4. **最新**: コード変更に合わせてドキュメントを更新
5. **アクセシビリティ**: 様々なスキルレベル向けに執筆

## ドキュメントへの貢献

ドキュメントを改善するには：

1. [貢献ガイド](../CONTRIBUTING.ja.md)に従う
2. 明確で簡潔な言葉を使用する
3. コード例を含める
4. UI機能のスクリーンショットを追加する
5. フォーマットの一貫性を保つ
6. すべてのコマンドと例をテストする

## ドキュメントメンテナンス

### 定期更新
- 四半期ごとに正確性をレビュー
- 新機能の追加に合わせて更新
- 報告された問題を修正
- コミュニティフィードバックの反映

### バージョン管理
- すべてのドキュメントはバージョン管理される
- 変更は[変更履歴](../CHANGELOG.ja.md)で追跡
- 主要な更新はリリースノートに記載

## ヘルプを得る

必要な情報が見つからない場合：

1. [FAQ](FAQ.ja.md)を確認する
2. [GitHub Issues](repository-url/issues)を検索する
3. [要件定義](../.kiro/specs/docker-mcp-gateway-console/requirements.md)を確認する
4. `documentation` ラベルを付けて新しいIssueを作成する

## フィードバック

ドキュメントへのフィードバックを歓迎します！以下をお願いします：

- 修正のためにIssueを作成する
- 改善のためにPRを送信する
- 新しいドキュメントトピックを提案する
- 不明確なセクションを報告する

---

**最終更新日**: 2024-12-06
**ドキュメントバージョン**: 1.0
