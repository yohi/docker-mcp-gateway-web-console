# Implementation Plan

## タスク概要

本実装計画は、docker-mcp-gateway-web-console の技術スタック最新化（Python 3.14、Node.js 22、Next.js 15、React 19）と DevContainer 環境の導入を段階的に実施するためのタスクリストである。全6要件をカバーし、既存テストスイートの維持を保証する。

---

## 実装タスク

### 1. DevContainer 環境の構築

- [ ] 1.1 (P) workspace サービス用 Dockerfile を作成
  - Python 3.14.0 と Node.js 22.12.0 を含む統合開発イメージを定義
  - 開発ツール（git, curl, docker CLI）をプリインストール
  - リポジトリルートをマウントするための作業ディレクトリ設定
  - _Requirements: 1.1, 1.4_

- [ ] 1.2 (P) devcontainer.json を作成
  - workspace サービスへの接続設定を定義
  - VS Code 拡張機能の推奨設定（Python, Pylance, Ruff, ESLint, Prettier, Tailwind）を含める
  - ポートフォワーディング設定（3000, 8000）を追加
  - postCreateCommand で Backend/Frontend 両方の依存関係をインストール
  - _Requirements: 1.2, 1.3, 1.4, 6.3_

- [ ] 1.3 (P) docker-compose.devcontainer.yml を作成
  - workspace サービスを定義し、リポジトリルートをマウント
  - Docker ソケットをマウント（rootless Docker 対応: `/run/user/$UID/docker.sock`）
  - backend/frontend サービスへの依存関係を設定
  - _Requirements: 1.1, 1.2, 1.4, 2.4_

- [ ] 1.4 DevContainer 環境の起動確認
  - VS Code で DevContainer を起動し、workspace コンテナに接続
  - Python 3.14 および Node.js 22 の実行確認
  - Backend/Frontend の依存関係解決を確認
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

### 2. Backend の Python 3.14 互換化

- [ ] 2.1 (P) Backend Dockerfile を Python 3.14 に更新
  - ベースイメージを `python:3.14.0-slim` に変更（パッチレベル固定）
  - C 拡張ビルド用の依存関係（build-essential, libffi-dev, libssl-dev）を追加
  - マルチステージビルドでビルド依存関係を最終イメージから除外
  - Dockerfile と Dockerfile.dev の両方を更新
  - _Requirements: 3.1, 3.4, 6.1, 6.2_

- [ ] 2.2 (P) Backend 依存関係を Python 3.14 互換に更新
  - requirements.txt のバージョンを `==` で完全固定（fastapi==0.115.6, pydantic==2.10.4 等）
  - pyproject.toml の target-version を `py314` に更新
  - Python 3.14 未対応のライブラリがあれば代替または更新
  - _Requirements: 3.2, 3.3_

- [ ] 2.3 Backend のビルドおよび起動確認
  - docker compose で backend サービスをビルド
  - Python 3.14 ランタイム上での起動を確認
  - healthcheck エンドポイント（/health）の動作確認
  - C 拡張を含む依存関係のビルド可否を確認
  - _Requirements: 3.1, 3.2, 3.4, 6.1, 6.2_

- [ ] 2.4 Backend テストスイートの実行
  - docker compose exec backend pytest でテストを実行
  - 全既存テストがパスすることを確認
  - テスト失敗時のログ出力を確認
  - _Requirements: 5.1, 6.1, 6.3_

### 3. Frontend の Node.js 22 / Next.js 15 / React 19 互換化

- [ ] 3.1 (P) Frontend Dockerfile を Node.js 22 に更新
  - 全ステージ（deps, builder, runner）のベースイメージを `node:22.12.0-alpine` に変更（パッチレベル固定）
  - マルチステージビルド構成を維持
  - standalone 出力の生成を確認
  - _Requirements: 4.1, 4.4, 6.1_

- [ ] 3.2 (P) Frontend 依存関係を Next.js 15 / React 19 に更新
  - package.json の依存関係を更新（next@15.1.3, react@19.0.0, react-dom@19.0.0）
  - CVE-2025-55183/55184 修正版（Next.js 15.1.3 以降）を使用
  - devDependencies の型定義を更新（@types/react@19.0.0, @types/react-dom@19.0.0）
  - `^` プレフィックスを除去し、完全固定
  - package-lock.json を生成してコミット
  - _Requirements: 4.2_

- [ ] 3.3 Next.js 15 の破壊的変更に対応
  - 公式 codemod を実行: `npx @next/codemod@canary upgrade latest`
  - Server Component の async params 対応（該当箇所がある場合）
  - useFormState → useActionState の移行（使用している場合）
  - 型エラーが発生した場合は個別に対応
  - _Requirements: 4.2, 4.3_

- [ ] 3.4 Frontend のビルドおよび起動確認
  - docker compose で frontend サービスをビルド
  - Node.js 22 ランタイム上での起動を確認
  - healthcheck の動作確認
  - ビルド失敗時のログ出力を確認
  - _Requirements: 4.1, 4.2, 4.4, 6.1_

- [ ] 3.5 Frontend テストスイートの実行
  - docker compose exec frontend npm test でユニットテストを実行
  - 全既存テストがパスすることを確認
  - テスト失敗時のログ出力を確認
  - _Requirements: 5.2, 6.1, 6.3_

### 4. テスト実行スクリプトの整備

- [ ] 4.1 (P) テスト実行スクリプトを作成
  - scripts/run-tests.sh を作成し、docker compose exec を使用したテスト実行を実装
  - backend/frontend/e2e/all の各テストモードをサポート
  - `-T` フラグで TTY を割り当てず、CI/CD 環境でも実行可能にする
  - `COMPOSE_FILE` 環境変数で異なる compose ファイルをサポート
  - _Requirements: 2.1, 2.2, 2.3, 1.4_

- [ ] 4.2 E2E テストの実行確認
  - docker compose exec frontend npm run test:e2e で E2E テストを実行
  - 主要ユーザーフロー（ログイン、コンテナ操作、カタログ閲覧）の動作確認
  - Playwright の実行環境を確認
  - _Requirements: 5.3, 6.3_

- [ ] 4.3 テストスクリプトの動作確認
  - ホストから scripts/run-tests.sh all を実行し、全テストがパスすることを確認
  - workspace コンテナから scripts/run-tests.sh all を実行し、同様に確認
  - cc-sdd からの呼び出しインターフェースを検証
  - _Requirements: 2.1, 2.2, 2.3, 6.3_

### 5. 統合検証とドキュメント更新

- [ ] 5.1 統合テストの実行
  - Backend API の起動確認（healthcheck）
  - Frontend の Backend API 接続確認
  - Docker ソケットアクセスの動作確認（rootless Docker 環境を含む）
  - DevContainer 内での開発サーバー起動確認
  - _Requirements: 1.4, 2.4, 6.3_

- [ ] 5.2 回帰テストの実行
  - 技術スタック更新前後でのテスト結果比較
  - 全既存テスト（Backend pytest, Frontend Jest, E2E Playwright）のパスを確認
  - テスト失敗がある場合は原因を特定し修正
  - _Requirements: 5.1, 5.2, 5.3, 6.3_

- [ ] 5.3 バージョン固定の最終確認
  - Python 3.14.x / Node.js 22.12.x / Next.js 15.1.x の最新パッチバージョンを確認
  - 実装開始時点で実在し、CVE 修正を満たすバージョンに確定
  - requirements.txt と package-lock.json のコミットを確認
  - _Requirements: 3.2, 4.2, 6.3_

- [ ] 5.4* ドキュメント更新（オプション）
  - README.md に DevContainer の使用方法を追記
  - docker-compose.yml の変更点を記載
  - テスト実行方法（scripts/run-tests.sh）を記載
  - _Requirements: 1.2, 2.3_

---

## 要件カバレッジ

| 要件 | カバーするタスク |
|------|-----------------|
| 1.1 | 1.1, 1.3, 1.4 |
| 1.2 | 1.2, 1.3, 1.4, 5.4* |
| 1.3 | 1.2, 1.4 |
| 1.4 | 1.1, 1.2, 1.3, 1.4, 4.1, 5.1 |
| 2.1 | 4.1, 4.3 |
| 2.2 | 4.1, 4.3 |
| 2.3 | 4.1, 4.3, 5.4* |
| 2.4 | 1.3, 5.1 |
| 3.1 | 2.1, 2.3 |
| 3.2 | 2.2, 2.3, 5.3 |
| 3.3 | 2.2 |
| 3.4 | 2.1, 2.3 |
| 4.1 | 3.1, 3.4 |
| 4.2 | 3.2, 3.3, 3.4, 5.3 |
| 4.3 | 3.3 |
| 4.4 | 3.1, 3.4 |
| 5.1 | 2.4, 5.2 |
| 5.2 | 3.5, 5.2 |
| 5.3 | 4.2, 5.2 |
| 6.1 | 2.1, 2.3, 2.4, 3.1, 3.4, 3.5 |
| 6.2 | 2.1, 2.3 |
| 6.3 | 1.2, 2.4, 3.5, 4.2, 4.3, 5.1, 5.2, 5.3 |

**全6要件（24受入基準）がカバーされています。**

---

## 実装順序の推奨

1. **Phase 1**: タスク 1.1〜1.4（DevContainer 環境構築）
2. **Phase 2**: タスク 2.1〜2.4（Backend 更新）と並行してタスク 3.1〜3.2（Frontend Dockerfile/依存関係更新）
3. **Phase 3**: タスク 3.3〜3.5（Frontend コード移行とテスト）
4. **Phase 4**: タスク 4.1〜4.3（テストスクリプト整備）
5. **Phase 5**: タスク 5.1〜5.4（統合検証とドキュメント）

並列実行可能なタスクには `(P)` マーカーを付与しています。
