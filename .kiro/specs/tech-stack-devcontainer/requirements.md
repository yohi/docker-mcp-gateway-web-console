# Requirements Document

## Introduction
本仕様は、docker-mcp-gateway-web-console に対して技術スタックの最新化（Backend: Python 3.14、Frontend: Node.js 22 / Next.js 15 / React 19）と DevContainer による統一開発環境の導入を行うための要件を定義する。

本書では、要件の主体（the [system]）として以下を用いる。
- **Backend Service**: FastAPI を提供し、バックエンド処理を担う。
- **Frontend Application**: Next.js による Web UI を提供する。
- **DevContainer Environment**: 開発者が利用する VS Code DevContainer の実行環境。
- **Build/Test Workflow**: ビルドおよびテスト実行を行う開発ワークフロー。

## Project Description (Input)
### 技術スタック最新化およびDevContainer導入 初期化仕様書

### 1. 概要と目的

本仕様書は、既存プロジェクト「docker-mcp-gateway-web-console」の技術スタックを最新バージョン（Python 3.14, Node.js 22, Next.js 15）へ刷新し、同時に開発環境の統一とテスト実行の安定性を担保するためのDevContainer環境を新規構築することを目的とする。これにより、開発効率の向上と最新機能の恩恵享受、および「cc-sdd」による自動開発プロセスの基盤確立を目指す。

### 2. 技術スタック

| 項目 | 内容 |
| :---- | :---- |
| バックエンド言語 | **Python 3.14** (本番運用可) |
| フロントエンド言語 | **Node.js 22** (Maintenance LTS: セキュリティ修正のみ) |
| フロントエンドフレームワーク | **Next.js 15**, React 19 (要: CVE 修正版の利用) |
| 開発形態 | 既存改修 (Brownfield) |
| コンテナランタイム | Docker (DevContainer経由) |

* **バージョン固定**: Python/Node/Next/React は **パッチ番号まで固定**（例: `x.y.z`）し、ロックファイルを必ずコミットする。
* **Python 3.14 互換性検証**: Python 3.14 は本番運用に耐えるが、C 拡張を含む依存（NumPy、cryptography、Cython/pybind11/PyO3 由来の拡張）の互換性を事前に確認する。採用前に CI で **ネイティブ拡張のビルド + import/実行テスト** を実施する。
* **Node.js アップグレード計画**: Node.js 22 は Maintenance LTS（セキュリティ修正のみ）のため、長期サポートに向けて **Node.js 24（または次期 LTS）への段階的移行**（期限・移行手順・検証項目）を定義する。
* **Next.js / React の脆弱性対応**: Next.js 15 / React 19 は既知の脆弱性（**CVE-2025-55183**、**CVE-2025-55184**）を踏まえ、**修正版（パッチ適用済みバージョン）の利用を必須**とする。CVE を継続的に監視し、依存関係監視と継続的アップグレード方針（緊急パッチ適用を含む）をポリシー化する。

* **固定バージョンの確定タイミングと更新ポリシー**: 設計内で例示する Python / Node.js / Next.js のバージョン（例: Python 3.14.2 / Node 22.12.0 / Next 15.1.11）は、**実装フェーズ開始前（Tasks生成完了時点）に Technical Lead が最終確定**し、実在かつCVE修正済みの最新パッチを選定する。確定後は、**セキュリティパッチ（CVE対応）のみ Technical Lead の承認により適用可能**とし、機能変更を伴う非セキュリティ更新は次期リリースまで禁止する。

### 3. 開発・テスト環境の制約 (重要)

* **DevContainer要件**: 
  * プロジェクトルートに `.devcontainer` ディレクトリを作成し、Backend/Frontend 両方の開発が可能な統合環境、もしくはそれぞれのサービスに適した構成を定義すること。
  * `devcontainer.json` には、VS Code拡張機能（Python, ESLint, Prettier等）の推奨設定を含めること。
* **テスト実行ポリシー**: 
  * すべての自動テスト（Unit, E2E）は、**必ずDevContainer内（またはDocker Compose環境内）でのみ実行すること**。
  * ホスト環境での直接的なランタイム実行（`python` や `npm` コマンド）は禁止とする。
  * `cc-sdd` ツール自体はホストOS上で稼働し、コンテナ内のテストランナーを起動する。
  * **標準実行方式は `docker compose exec`** とする。`docker compose exec` はサービスを直接実行するCI/CDやスクリプト自動化に適しており、`devcontainer exec` はIDE連携・ユーザーコンテキスト/SSH鍵転送をサポートするローカル向け方式である。
  * **`docker compose exec` を標準にする理由**: CI/CD環境およびスクリプト自動化との互換性を確保し、環境非依存のテスト実行を実現するため。
  * **`devcontainer exec` の許容シナリオ**: ローカルIDE（VS Code）での開発・デバッグ時のみ許可する。CI/CD環境や自動化スクリプトでは使用不可とする。
  * **実装参照**: `tasks.md` で定義される `scripts/run-tests.sh` は `docker compose exec` を使用しており、本要件との整合性を保つ。
  * **Docker ソケット前提**: 開発者環境が rootless Docker の場合、workspace から Docker を操作するための標準ソケットパスとして `/run/user/$UID/docker.sock` を前提にできること。

### 4. 機能要件詳細

#### 4.1. Backend (Python) 更新
* **ベースイメージの変更**: `backend/Dockerfile` のベースイメージを Python 3.14 系に変更する。
* **依存関係の更新**: `pyproject.toml` および `requirements.txt` を更新し、Python 3.14 との互換性を確保する。
  * 主要ライブラリ（FastAPI, Pydantic等）のバージョンアップが必要な場合は実施する。
  * 3.14未対応のライブラリがある場合は、代替手段の検討または互換性のある最新版を選定する。

#### 4.2. Frontend (Node.js/Next.js) 更新
* **ベースイメージの変更**: `frontend/Dockerfile` のベースイメージを Node.js 22 (Alpine等) に変更する。
* **フレームワーク更新**: `package.json` を修正し、Next.js を v15、React を v19 にアップデートする。
* **コード修正**: メジャーバージョンアップに伴う破壊的変更（Breaking Changes）がある場合、既存コード（App Router等）の修正を行う。

#### 4.3. DevContainer環境の構築
* **設定ファイルの作成**:
  * `.devcontainer/devcontainer.json`: 開発コンテナの定義。
  * `.devcontainer/docker-compose.yml` (必要に応じて): 開発用サービス（DB等含む）のオーケストレーション。
* **開発体験の向上**:
  * シェル設定（bash/zsh）や、Git設定の引き継ぎ等を考慮する。
  * 必要なCLIツール（uv, npm等）がプリインストールされた状態にすること。

### 5. その他の仕様

* **互換性検証**: Python 3.14 はリリース直後の最新版であるため、C拡張を含むライブラリのインストール可否を重点的に確認し、ビルドエラーが発生した場合はログを詳細に記録すること。
* **既存テストのパス**: 技術スタック更新後も、既存のテストスイート（`pytest`, `jest/playwright`）がすべてパスすることを完了条件とする。

## Requirements
### Requirement 1: DevContainer 環境の提供
**Objective:** As a 開発者, I want DevContainer でプロジェクトを再現可能に起動できる, so that ホスト環境差異なく開発を開始できる

#### Acceptance Criteria
1. When 開発者が DevContainer を起動したとき, the DevContainer Environment shall Backend/Frontend の開発に必要な実行環境（Python 3.14、Node.js 22）を提供する
2. The DevContainer Environment shall リポジトリルートに配置された DevContainer 設定（`.devcontainer`）により再現可能に定義される
3. When DevContainer が起動したとき, the DevContainer Environment shall Python/TypeScript 開発に必要な VS Code 拡張機能の推奨設定を提供する
4. The DevContainer Environment shall Backend と Frontend の依存関係解決、開発サーバー起動、テスト実行をコンテナ内で実行できる

### Requirement 2: テスト実行ポリシー（コンテナ内実行の強制）
**Objective:** As a 開発者, I want すべての自動テストをコンテナ内で実行できる, so that 実行環境差異による不安定さを排除できる

#### Acceptance Criteria
1. The Build/Test Workflow shall 単体テストおよび E2E テストを DevContainer 内（または Docker Compose 環境内）で実行できる
2. The Build/Test Workflow shall ホスト環境での直接的なランタイム実行（`python` や `npm` によるテスト実行）を前提としない
3. When `cc-sdd` が自動テストを実行するとき, the Build/Test Workflow shall ホストから `docker compose exec` を直接実行してコンテナ内のテストランナーを起動する
4. When 開発者環境が rootless Docker であるとき, the Build/Test Workflow shall workspace から Docker を操作するために `/run/user/$UID/docker.sock` を標準ソケットパスとして利用できる
5. When Docker Compose サービス起動に失敗したとき, the Build/Test Workflow shall 以下のフォールバック手順を実行する:
   - 最大3回まで再起動を試行する（試行間隔: 5秒のバックオフ）
   - 再起動失敗時は代替実行モード（devcontainer exec による実行）を試行する
   - すべての試行が失敗した場合は **フェイルビルド** ステータスで終了し、明確なエラーメッセージを出力する
6. When `docker compose exec` コマンドが失敗したとき, the Build/Test Workflow shall 以下のリトライポリシーを適用する:
   - 最大3回までコマンドを再試行する（試行間隔: 2秒の固定バックオフ）
   - 各試行でエラー理由（コンテナ停止、ネットワーク障害等）をログに記録する
   - 最大試行回数到達後は **フェイルビルド** ステータスで終了し、失敗通知を出力する
7. When TTY 割り当てエラーが発生したとき, the Build/Test Workflow shall 以下の対応を行う:
   - CI 環境（環境変数 `CI=true` または `TERM=dumb` を検出）では `-T` フラグを自動付与して TTY なしモードで実行する
   - ローカル環境では TTY を必須とし、割り当て失敗時は **警告を出力して継続**する（デバッグ出力の見やすさを優先）
   - TTY 判定ロジックは環境変数および標準入力の isatty チェックにより実装する

### Requirement 3: Backend の Python 3.14 互換化
**Objective:** As a 開発者, I want Backend Service が Python 3.14 でビルドおよび起動できる, so that 最新ランタイムで継続的に保守できる

#### Acceptance Criteria
1. The Backend Service shall Python 3.14 ランタイム上で起動できる
2. The Backend Service shall Python 3.14 と互換性のある依存関係でインストールおよび起動できる
3. If Python 3.14 未対応の依存関係が存在するとき, then the Backend Service shall 代替または更新により Python 3.14 互換性を確保する
4. The Backend Service shall Python 3.14 を含むコンテナ環境でビルド可能である

### Requirement 4: Frontend の Node.js 22 / Next.js 15 / React 19 互換化
**Objective:** As a 開発者, I want Frontend Application が Node.js 22 と Next.js 15 / React 19 でビルドおよび起動できる, so that 最新フレームワークで開発できる

#### Acceptance Criteria
1. The Frontend Application shall Node.js 22 ランタイム上で依存関係解決、ビルド、および起動が成功する
2. The Frontend Application shall Next.js 15 / React 19 の互換性を満たす
3. If フレームワーク更新に伴う破壊的変更によりビルドまたは起動が失敗するとき, then the Frontend Application shall 既存の機能を維持したまま互換性を回復する
4. The Frontend Application shall Node.js 22 を含むコンテナ環境でビルド可能である

### Requirement 5: 回帰防止（既存テストスイートの維持）
**Objective:** As a プロジェクトオーナー, I want 技術スタック更新後も既存機能が回帰しない, so that 安全に継続運用できる

#### Acceptance Criteria
1. When 技術スタック更新が完了したとき, the Backend Service shall 既存の自動テストスイート（pytest 等）がすべてパスする
2. When 技術スタック更新が完了したとき, the Frontend Application shall 既存の自動テストスイート（Jest 等）がすべてパスする
3. When E2E テストが実行されるとき, the Frontend Application shall 既存の主要ユーザーフローが期待どおりに動作することを検証できる

### Requirement 6: 互換性検証と障害解析可能性
**Objective:** As a 開発者, I want 更新に伴うビルド・依存関係の失敗を迅速に特定できる, so that 修正に必要な情報を得られる

#### Acceptance Criteria
1. If 依存関係のインストールまたはビルドが失敗したとき, then the Build/Test Workflow shall 失敗理由を特定できるログを出力する
2. While Python 3.14 の互換性検証を行っているとき, the Build/Test Workflow shall C 拡張を含む依存関係のビルド可否を重点的に確認できる
3. The Build/Test Workflow shall 更新後のビルドおよびテスト実行結果を、再現可能な形で開発者が確認できる
