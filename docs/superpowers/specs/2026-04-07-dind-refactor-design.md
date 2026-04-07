# Docker MCP Gateway Console - アーキテクチャ・リファクタリング設計書

## 1. 目的と背景

本ドキュメントは、`docker-mcp-gateway-console` プロジェクトにおけるコンテナ管理アーキテクチャの刷新と、バックエンドAPI層の責務分離に関する設計を定義するものです。

現状のシステムは、開発環境（Devcontainer）においてホストマシンの Docker デーモン（`docker.sock`）を直接マウントする **DooD (Docker-out-of-Docker)** アプローチを採用しています。これはローカル開発においては簡便ですが、以下の課題を抱えています。
1. **セキュリティリスク**: ホストのDockerデーモンへのフルアクセスを許容するため、コンテナからの権限昇格（Privilege Escalation）のリスクが存在する。
2. **クラウドネイティブとの乖離**: Kubernetes (k8s) や Amazon ECS などの本番環境では、ソケットマウントによるコンテナ管理はアンチパターンであり、リモートAPI経由や専用のオーケストレーション機構への移行が困難。
3. **バックエンドの責務混在**: FastAPIのルーター層（`app/api/`）にビジネスロジック（セッション検証、コンテナ作成の事前処理など）が混在しており、テスト容易性と保守性が低下している。

これらの課題を解決するため、セキュアなコンテナ管理アーキテクチャへの移行と、DI（Dependency Injection）を活用したバックエンドの責務分離を実施します。

---

## 2. アーキテクチャ刷新案: DinD と TLS Remote API

DooD アプローチから脱却し、**Docker-in-Docker (DinD)** を用いた独立したコンテナ環境と、TLSで保護された **Docker Remote API** 経由での通信モデルへ移行します。

### 2.1. 構成の比較

**【現状 (DooD)】**
- Workspace (Devcontainer) コンテナに `${DOCKER_SOCKET}:/var/run/docker.sock` をマウント。
- Backend (FastAPI) はローカルの UNIX ソケット経由でホストのコンテナを操作。

**【新構成 (DinD + TLS)】**
- `docker:dind` イメージを用いた独立した `dind` サービスをサイドカーとして立ち上げる。
- `dind` サービスは TLS 証明書を自動生成し、TCPポート（2376）で Docker Remote API を公開する。
- Workspace および Backend は、共有ボリューム経由で TLS クライアント証明書を取得し、`DOCKER_HOST=tcp://dind:2376` を経由してセキュアにコンテナ操作を行う。

### 2.2. メリット
- **セキュリティの向上**: ホスト環境へのアクセスを完全に遮断し、操作対象を `dind` コンテナ内部に限定。
- **本番環境への親和性**: TLS通信モデルを採用することで、本番環境においてセキュアなリモートDockerホストや、k8sの専用DaemonSetへの接続にシームレスに切り替え可能。
- **再現性の向上**: ホストマシンのDocker環境への依存がなくなり、クリーンなコンテナ実行環境を保証。

---

## 3. 詳細な変更内容

### 3.1. Devcontainer 環境の更新

ホストのソケットマウントを廃止し、`dind` サービスを追加します。

**`docker-compose.devcontainer.yml` の変更方針:**
- `workspace` サービスの `volumes` から `${DOCKER_SOCKET}:/var/run/docker.sock` を削除。
- 新規サービス `dind` (image: `docker:dind`) を追加し、`privileged: true` およびTLS証明書生成用のボリューム設定を行う。
- `workspace` および `backend` サービスに、`dind` と通信するための環境変数 (`DOCKER_HOST`, `DOCKER_TLS_VERIFY`, `DOCKER_CERT_PATH`) と証明書マウントを追加。

**`.devcontainer/devcontainer.json` の変更方針:**
- VSCodeのDocker拡張機能が正しく接続できるよう、`remoteEnv` に `DOCKER_HOST`, `DOCKER_TLS_VERIFY`, `DOCKER_CERT_PATH` を設定。

### 3.2. バックエンドの責務分離 (DI と Service 層の強化)

FastAPIルーターに散在しているロジックを `ContainerService` に集約し、Thin Controller パターンを徹底します。

**1. `AuthService` のインジェクション (`app/services/containers.py`)**
- `ContainerService` のコンストラクタに `AuthService` を追加。
- セッションの検証と取得を行うプライベートメソッド（例: `_validate_session_and_get`）を実装。
- APIから直接呼ばれるユースケース向けに、認証付きのオーケストレーションメソッド（`create_container_with_auth`, `list_containers_with_auth` など）を新設。

**2. APIルーターの簡略化 (`app/api/containers.py`)**
- `get_container_service` の依存関係に `AuthService` を追加し、`ContainerService` に注入。
- `_create_container_internal` のようなルーター内のヘルパー関数を削除。
- 各エンドポイントは、リクエストパラメータを受け取り、`ContainerService` の対応するメソッドを呼び出し、レスポンスモデルを返すだけの処理に徹する。

---

## 4. 制約と後方互換性

- **APIスキーマの維持**: `app/schemas/` (または `app/models/`) に定義されている `ContainerConfig`, `ContainerListResponse` などのリクエスト/レスポンスモデルには一切変更を加えません。
- **ステート管理の維持**: `app/models/state.py` で定義されているデータベース/ステートの保存形式は維持されます。
- **フロントエンドの無変更**: APIの振る舞い（エンドポイント、ペイロード、ステータスコード）が完全に維持されるため、Next.js/React 側の改修は不要です。
- **Devcontainerの強制**: すべてのテスト（pytest, Playwright）や静的解析（Ruff, ESLint）は、この新しい DinD 環境上で従来通り実行されるようにします。ネットワーク層が TCP に変わるだけで、Docker Python SDK (`docker.tls.TLSConfig` を利用) により透過的に処理されます。

## 5. 実行ステップ (Implementation Plan)

1. **Devcontainerインフラの更新**: `docker-compose.devcontainer.yml` と `devcontainer.json` を更新し、DinD環境を構築。
2. **バックエンドサービス層の拡張**: `app/services/containers.py` を修正し、認証ロジックを統合したメソッドを追加。
3. **バックエンドAPIルーターのクリーンアップ**: `app/api/containers.py` をリファクタリングし、Service層への委譲のみを行う Thin Controller に変更。
4. **検証 (Validate)**: Devcontainerをリビルドし、バックエンドのユニットテスト、フロントエンドのE2Eテストがすべて通過することを確認する。

---
*設計作成日: 2026年4月7日*
*作成者: シニア・ソフトウェアアーキテクト*
