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
- Workspace (Devcontainer) コンテナにホストの Docker ソケットをマウント。
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
- `workspace` サービスの `volumes` からホスト Docker ソケットのマウントを削除。
- 新規サービス `dind` (image: `docker:dind`) を追加し、`privileged: true` およびTLS証明書生成用のボリューム設定を行う。
- **データとキャッシュの永続化**: `dind` コンテナの再作成時にダウンロード済みのDockerイメージやビルドキャッシュが失われ、開発体験（ビルド速度）が著しく低下するのを防ぐため、名前付きボリューム（例: `dind-data:/var/lib/docker`）をマウントし、Dockerの内部データやイメージキャッシュを永続化する設定を追加します。
- `workspace` および `backend` サービスに、`dind` と通信するための環境変数 (`DOCKER_HOST`, `DOCKER_TLS_VERIFY`, `DOCKER_CERT_PATH`) を設定します。設定齟齬を防ぐため、`dind` サービスが自動生成するTLSクライアント証明書の共有ディレクトリパスを `/certs/client` と明記し、各サービスはこのディレクトリを同一パス（または指定のパス）でボリュームマウントして証明書を参照するよう構成します。
- **Race Condition（起動順序）の解決**: `dind` サービスがTLS証明書を生成してリスン状態になる前に他のサービスがアクセスしてクラッシュするのを防ぐため、`dind` サービスに `healthcheck`（例: TCPポート2376への接続確認等）を追加します。同時に `workspace` および `backend` サービスには `depends_on` で `condition: service_healthy` を指定し、安全な起動順序を保証します。
- **DinDのネットワーク課題の解決**: DinD内で作成されたコンテナは `dind` コンテナのネットワーク名前空間に隔離されるため、`workspace` やホストOSから直接アクセスできません。YAGNI原則に基づき、開発環境として最もシンプルで確実な一次解決策として、`dind` サービスにおいてあらかじめ必要なポート範囲（例: `8080-8090:8080-8090`）をホスト側にパブリッシュ（ポートフォワード）する構成を採用します。

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

### 3.3. 異常系・エッジケースの考慮

インフラ移行に伴い、以下の異常系に対するフェイルセーフな振る舞いと開発者向けのエラーログ出力方針を定義します。

- **`DOCKER_HOST` への接続タイムアウト**: バックエンド（`ContainerService` 等）から `dind` サービスへの接続要求がタイムアウトした場合、システム全体をクラッシュさせず、適切な HTTP 503 (Service Unavailable) などのエラーレスポンスをフロントエンドに返却します。同時に、開発者が原因を即座に特定できるよう、接続先URLを含む詳細なエラーログを出力します。
- **TLS証明書の生成失敗（`dind`初期化エラー）**: `dind` サービスの起動時にTLS証明書の生成に失敗した場合、前述の `healthcheck` により `dind` は unhealthy となり、依存する `workspace` や `backend` の起動がブロックされます。この際、`docker-compose logs dind` 等で証明書生成プロセスのエラー原因（権限エラー、ボリュームマウント不備など）が確認できるよう、コンテナの初期化ログを標準出力に適切に流すよう構成します。
- **ステート乖離（リコンサイル）の考慮**: DooDからDinDへの分離により、バックエンド（DBのステート）とDinDデーモンのコンテナ状態が、コンテナ再起動時などに乖離するリスク（例: DB上は稼働中だが、DinD上には存在しない等）が高まります。この問題への対処として、バックエンドの起動時やコンテナ情報取得API（List/Get）の呼び出し時に、実際のDinDホスト上のコンテナ状態とDBのステートを同期（リコンサイル）する軽量な仕組みを導入します。過剰な実装（常時ポーリング等の複雑な同期機構）は避け、YAGNI原則の範囲内で、APIアクセス時のオンデマンド同期や、乖離検知時のリカバリ（DBステータスを `exited` や `error` に更新し、警告ログを出力する）にとどめます。

---

## 4. 制約と後方互換性

- **APIスキーマの維持**: `app/schemas/` (または `app/models/`) に定義されている `ContainerConfig`, `ContainerListResponse` などのリクエスト/レスポンスモデルには一切変更を加えません。
- **ステート管理の維持**: `app/models/state.py` で定義されているデータベース/ステートの保存形式は維持されます。
- **フロントエンドの無変更**: APIの振る舞い（エンドポイント、ペイロード、ステータスコード）が完全に維持されるため、Next.js/React 側の改修は不要です。
- **Devcontainerの強制**: すべてのテスト（pytest, Playwright）や静的解析（Ruff, ESLint）は、この新しい DinD 環境上で従来通り実行されるようにします。ネットワーク層が TCP に変わるだけで、Docker Python SDK (`docker.tls.TLSConfig` を利用) により透過的に処理されます。

## 5. 実行ステップ (Implementation Plan)

ビジネスロジックの変更とインフラの変更を同時に行うと、テスト失敗時の原因切り分けが困難になります。そのため、本プロジェクトの Superpowers Workflow（TDDベース）に則り、インフラ移行（DinD化）を先に行い、既存テストがリモートAPI経由でGreenになることを確認してから、Service層のTDDリファクタリングに着手する順序（案B）を採用します。

1. **既存テストの確認 (Baseline)**: 現在の DooD 環境で既存のバックエンドテストやE2Eテストを実行し、すべてパスすること（Green）を確認する。
2. **インフラの DinD 移行**: `docker-compose.devcontainer.yml` と `devcontainer.json` を更新し、DinD 環境を構築する。この段階ではバックエンドのビジネスロジックは一切変更しない。
3. **インフラ移行の検証 [Green]**: DinD 環境上で既存のテストを再実行し、リモートAPI経由でもテストがすべてパスすることを確認する。この際、テストランナー（Pytest等）が新しい `DOCKER_HOST` と `DOCKER_CERT_PATH` を正しく認識できるよう、テスト起動時の `.env.test` の読み込みや、テストフィクスチャによる環境変数のモック適用を確実に行います。これによりインフラ起因の問題がないことを保証する。
4. **Service層のテスト作成 [Red]**: `app/services/containers.py` に Auth 連携などの新しい責務に関するテストを追加し、テストが失敗することを確認する。
5. **Service層の実装 [Green]**: `ContainerService` 内に認証・ビジネスロジックを実装し、テストを成功させる。
6. **APIルーターのリファクタリング [Refactor]**: ルーター層（`app/api/containers.py`）からビジネスロジックを削除し、Thin Controller 化する。最後に全体のユニットテストおよびフロントエンドのE2Eテストがすべて通過することを確認し、検証を完了する。

---
*設計作成日: 2026年4月7日*
*作成者: シニア・ソフトウェアアーキテクト*
