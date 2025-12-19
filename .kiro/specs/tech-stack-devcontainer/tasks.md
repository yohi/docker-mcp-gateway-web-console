# Implementation Plan

## タスク概要

本実装計画は、docker-mcp-gateway-web-console の技術スタック最新化（Python 3.14、Node.js 22、Next.js 15、React 19）と DevContainer 環境の導入を段階的に実施するためのタスクリストである。全6要件をカバーし、既存テストスイートの維持を保証する。

---

## 実装タスク

### 1. DevContainer 環境の構築

- [x] 1.1 (P) workspace サービス用 Dockerfile を作成
  - Python 3.14.0 と Node.js 22.12.0 を含む統合開発イメージを定義
  - 開発ツール（git, curl, docker CLI）をプリインストール
  - リポジトリルートをマウントするための作業ディレクトリ設定
  - **成功基準**:
    - Dockerfile が正常にビルドされる（`docker build` が exit code 0 で完了）
    - ビルド後のイメージサイズが 2GB 以下である
    - イメージに Python 3.14.x が含まれる（`python --version` が `Python 3.14.` で始まる）
    - イメージに Node.js 22.12.x が含まれる（`node --version` が `v22.12.` で始まる）
    - git, curl, docker CLI が実行可能である（`which git && which curl && which docker` が成功）
  - **検証方法**: `docker build -t workspace:test . && docker images workspace:test --format "{{.Size}}" && docker run --rm workspace:test python --version && docker run --rm workspace:test node --version && docker run --rm workspace:test sh -c "which git && which curl && which docker"`
  - _Requirements: 1.1, 1.4_

- [x] 1.2 (P) devcontainer.json を作成
  - workspace サービスへの接続設定を定義
  - VS Code 拡張機能の推奨設定（Python, Pylance, Ruff, ESLint, Prettier, Tailwind）を含める
  - ポートフォワーディング設定（3000, 8000）を追加
  - postCreateCommand で Backend/Frontend 両方の依存関係をインストール
  - **成功基準**:
    - devcontainer.json が JSON 形式として有効である（構文エラーなし）
    - VS Code が devcontainer.json を認識し、「Reopen in Container」オプションが表示される
    - `customizations.vscode.extensions` に少なくとも6つの拡張機能がリストされている（Python, Pylance, Ruff, ESLint, Prettier, Tailwind CSS IntelliSense）
    - `forwardPorts` に 3000 と 8000 が含まれる
    - `postCreateCommand` が定義されている
  - **検証方法**: `jq empty .devcontainer/devcontainer.json && jq '.customizations.vscode.extensions | length >= 6' .devcontainer/devcontainer.json && jq '.forwardPorts | contains([3000, 8000])' .devcontainer/devcontainer.json && jq '.postCreateCommand' .devcontainer/devcontainer.json` およびVS Code での実際の認識確認
  - _Requirements: 1.2, 1.3, 1.4, 6.3_

- [x] 1.3 (P) docker-compose.devcontainer.yml を作成
  - workspace サービスを定義し、リポジトリルートをマウント
  - **Docker ソケットマウント（rootless/rootful 両対応）**:
    - **検出優先順位**: `$XDG_RUNTIME_DIR/docker.sock` → `/run/user/$UID/docker.sock` → `/var/run/docker.sock`
    - **実装方法**: devcontainer 初期化スクリプト（`.devcontainer/init-docker-socket.sh`）を作成し、以下のロジックを実装:
      ```bash
      # rootless Docker ソケット検出（優先）
      if [ -S "${XDG_RUNTIME_DIR:-/run/user/$UID}/docker.sock" ]; then
        DOCKER_SOCKET="${XDG_RUNTIME_DIR:-/run/user/$UID}/docker.sock"
      # rootful Docker ソケットへフォールバック
      elif [ -S "/var/run/docker.sock" ]; then
        DOCKER_SOCKET="/var/run/docker.sock"
      # ソケットが見つからない場合はエラーで中断
      else
        echo "ERROR: Docker socket not found. Checked:" >&2
        echo "  - ${XDG_RUNTIME_DIR:-/run/user/$UID}/docker.sock" >&2
        echo "  - /var/run/docker.sock" >&2
        exit 1
      fi
      ```
    - compose ファイルでは環境変数 `${DOCKER_SOCKET}` を使用してソケットをマウント
  - backend/frontend サービスへの依存関係を設定
  - **成功基準**:
    - YAML ファイルが構文的に有効である（yamllint でエラーなし）
    - `docker compose -f docker-compose.devcontainer.yml config` が成功する
    - Docker ソケット検出スクリプト（`init-docker-socket.sh`）が存在し、実行可能である
    - rootless 環境では `$XDG_RUNTIME_DIR/docker.sock` または `/run/user/$UID/docker.sock` が優先的に使用される
    - rootful 環境では `/var/run/docker.sock` が使用される
    - ソケットが存在しない場合、スクリプトが明確なエラーメッセージを出力して exit 1 で終了する
    - workspace サービスがリポジトリルートをマウントしている（`.:/workspace` または同等の設定）
    - workspace サービスが backend/frontend サービスに依存している（`depends_on` に backend, frontend が含まれる）
  - **検証方法**:
    - YAML 検証: `yamllint docker-compose.devcontainer.yml && docker compose -f docker-compose.devcontainer.yml config`
    - ソケット検出テスト（rootless）: `XDG_RUNTIME_DIR=/run/user/$(id -u) .devcontainer/init-docker-socket.sh && echo "Detected: $DOCKER_SOCKET"`
    - ソケット検出テスト（rootful）: `XDG_RUNTIME_DIR=/nonexistent .devcontainer/init-docker-socket.sh && echo "Detected: $DOCKER_SOCKET"`
    - エラーハンドリングテスト: `XDG_RUNTIME_DIR=/nonexistent .devcontainer/init-docker-socket.sh` （rootful ソケットも存在しない環境で実行し、exit 1 とエラーメッセージを確認）
  - _Requirements: 1.1, 1.2, 1.4, 2.4_

- [x] 1.4 DevContainer 環境の起動確認スクリプト実装
  - VS Code で DevContainer を起動し、workspace コンテナに接続
  - Python 3.14 および Node.js 22 の実行確認
  - Backend/Frontend の依存関係解決を確認
  - **成功基準**:
    - VS Code で DevContainer が正常に起動し、workspace コンテナに接続できる
    - `python --version` が `Python 3.14.` で始まる出力を返す
    - `node --version` が `v22.12.` で始まる出力を返す
    - Backend 依存関係: `pip list | grep fastapi` が成功し、FastAPI がインストールされている
    - Frontend 依存関係: `npm list next --prefix frontend` が成功し、Next.js がインストールされている
    - postCreateCommand が正常に完了し、exit code 0 で終了している
  - **検証方法**: DevContainer 内で以下のコマンドを実行: `python --version && node --version && pip list | grep fastapi && npm list next --prefix frontend && echo "postCreateCommand status: $?" `
  - **自動チェックスクリプト**: `scripts/verify-devcontainer.sh` を作成し、以下を検証:
    - ランタイムバージョン確認（Python 3.14.x, Node.js 22.12.x）
    - Backend 依存関係（FastAPI, Pydantic, uvicorn）
    - Frontend 依存関係（Next.js, React, TypeScript）
    - VS Code 拡張機能のインストール状態
  - _Requirements: 1.1, 1.2, 1.3, 1.4_


### 2. Backend の Python 3.14 互換化

- [x] 2.1 (P) Backend Dockerfile を Python 3.14 に更新
  - **マルチステージビルド構成（本番用 Dockerfile）**:
    - **builder ステージ**:
      - ベースイメージ: `python:3.14.0-slim`
      - ビルド専用パッケージをインストール（apt-get）: `build-essential`, `libffi-dev`, `libssl-dev`, `gcc`, `make`, `pkg-config`, `python3-dev`
      - pip wheel ビルドのキャッシュを有効化（`--mount=type=cache,target=/root/.cache/pip`）
      - frozen requirements.txt から依存関係をビルドし、wheel/dist を生成
      - ビルド成果物を `/wheels` ディレクトリに配置
    - **runtime ステージ（最終イメージ）**:
      - ベースイメージ: `python:3.14.0-slim`
      - ランタイム専用パッケージをインストール（apt-get）: `libffi8`, `libssl3`（slim パッケージ経由で必要最小限）
      - builder ステージから `/wheels` をコピー
      - frozen requirements.txt から最小限の pip インストールを実行（`--no-cache-dir --no-index --find-links=/wheels`）
      - ビルド依存関係は一切含めない
  - **イメージサイズ削減目標**:
    - 現在のシングルステージイメージと比較して **30%以上** のサイズ削減を達成
    - **測定方法**: `docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"` で更新前後のサイズを比較
  - **開発用 Dockerfile.dev**:
    - 本番用 Dockerfile の builder + runtime ステージをベースとする
    - **dev ステージ** を追加（runtime ステージから派生）:
      - dev専用の依存関係とツールをインストール: `debugpy`（Python デバッガ）, `ruff`（リンター）, `pytest`, `pytest-cov`（テストフレームワーク）
      - 開発用ツールは requirements-dev.txt から管理
    - **用途**: ローカル開発専用（DevContainer 内で使用）
    - 最終イメージにはdev依存関係を含めない（本番用は runtime ステージで終了）
  - **チェックリスト**:
    - [x] builder ステージが明示的に定義され、`FROM python:3.14.0-slim AS builder` で開始する
    - [x] builder ステージのビルドパッケージリスト（7個）: `build-essential`, `libffi-dev`, `libssl-dev`, `gcc`, `make`, `pkg-config`, `python3-dev`
    - [x] runtime ステージが明示的に定義され、`FROM python:3.14.0-slim AS runtime` で開始する
    - [x] runtime ステージのランタイムパッケージリスト（2個）: `libffi8`, `libssl3`
    - [x] `COPY --from=builder /wheels /wheels` で成果物をコピーしている
    - [x] イメージサイズ比較コマンドを実行し、削減率を記録: `docker build -t backend:before -f Dockerfile.old . && docker build -t backend:after -f Dockerfile . && docker images --format "{{.Repository}}:{{.Tag}} {{.Size}}" | grep backend`
      - 計測結果（backend/ ディレクトリで実行, 2025-12-18）: `backend:before 745MB`, `backend:after 346MB` → **削減率 約54%**
    - [x] Dockerfile.dev に dev ステージが定義され、`FROM runtime AS dev` で開始する
    - [x] Dockerfile.dev の dev専用パッケージリスト（4個）: `debugpy`, `ruff`, `pytest`, `pytest-cov`
  - _Requirements: 3.1, 3.4, 6.1, 6.2_

- [x] 2.2 (P) Backend 依存関係を Python 3.14 互換に更新
  - **依存関係の完全固定（2段階アーティファクト管理）**:
    - **(a) requirements.in**: 直接依存のみを厳密なバージョンで記載
      - 形式: `package==x.y.z`（例: `fastapi==0.115.6`, `pydantic==2.10.4`）
      - **編集ルール**: 依存関係の追加・更新は requirements.in に対してのみ実施
    - **(b) requirements.txt**: 推移的依存を含む完全固定版（自動生成）
      - **生成方法**: pip-tools (`pip-compile requirements.in`) または Poetry (`poetry export --format requirements.txt`)
      - **CI/CD での再生成**: PR 作成時に CI が requirements.txt を再生成し、差分をコミット
      - **手動編集禁止**: requirements.txt への直接編集は行わず、必ず requirements.in 経由で更新
    - **アップグレード手順**:
      1. requirements.in でバージョンを更新
      2. `pip-compile --upgrade --generate-hashes requirements.in` を実行（ローカル）
      3. 生成された requirements.txt を確認
      4. PR を作成し、CI で再生成検証
  - **開発ツールの target-version 設定（Python 3.14 対応）**:
    - リポジトリで使用している各ツールの pyproject.toml 設定を更新:
      - **Black**:
        ```toml
        [tool.black]
        target-version = ["py314"]
        ```
      - **Ruff**:
        ```toml
        [tool.ruff]
        target-version = "py314"
        ```
      - **MyPy**:
        ```toml
        [tool.mypy]
        python_version = "3.14"
        ```
        （または CLI フラグ: `mypy --python-version=3.14`）
      - **Pytest**（pyproject.toml または pytest.ini）:
        ```toml
        [tool.pytest.ini_options]
        python_version = "3.14"
        ```
      - **その他のツール**: リポジトリで使用している全ツール（例: isort, bandit, coverage）について、Python バージョン指定の設定キー/値を列挙し更新
  - **Python 3.14 未対応ライブラリの対処方法**:
    - **優先順位**: サポート版へのメジャーアップグレードを最優先（例: Pydantic v1 → v2）
    - **マイグレーションチェックリスト**（Pydantic v2 への移行例）:
      - [ ] `BaseModel.dict()` → `BaseModel.model_dump()` に置換
      - [ ] `BaseModel.parse_obj()` → `BaseModel.model_validate()` に置換
      - [ ] `@validator` → `@field_validator` + `@model_validator` に移行
      - [ ] `Config` クラス → `model_config = ConfigDict(...)` に移行
      - [ ] 型アノテーションの更新（`Optional[X]` → `X | None` 等、Python 3.10+ 構文）
    - **互換性テストマトリクス**:
      - CI に Python 3.14 専用ジョブを追加（`.gitlab-ci.yml` または `.github/workflows/`）:
        ```yaml
        test-python314:
          image: python:3.14.0-slim
          script:
            - pip install -r requirements.txt
            - pytest tests/
            - python -m mypy src/
        ```
    - **検証手順**:
      1. ユニットテスト実行: `pytest tests/ --cov`
      2. 統合テスト実行: `pytest tests/integration/`
      3. DevContainer スモークラン: `docker compose -f docker-compose.devcontainer.yml up backend` → healthcheck 確認
      4. CI グリーン確認: 全テストマトリクスジョブがパス
  - **承認フロー**:
    - **PR 作成要件**:
      - [ ] 変更ログ（CHANGELOG.md または PR 本文）: 更新した依存関係のバージョン一覧と理由
      - [ ] マイグレーションノート（MIGRATION.md または PR 本文）: 破壊的変更とコード修正内容
      - [ ] テスト結果: ローカルおよび CI でのテスト実行ログ（pytest カバレッジレポート、MyPy 出力）
      - [ ] CI グリーン: 全ジョブ（lint, test, build）が成功
    - **必須レビュアー**:
      - Backend Tech Lead: 技術的妥当性とマイグレーション戦略の承認
      - Security/Operations レビュアー: セキュリティリスク（CVE 対応状況）とデプロイ影響の承認
    - **決定事項の記録**: PR 説明（Description）に以下を記載:
      - アップグレードの動機（例: Python 3.14 サポート、CVE-2024-XXXXX 修正）
      - 検証結果サマリー（テストカバレッジ %, CI 実行時間）
      - ロールバック計画（問題発生時の切り戻し手順）
  - _Requirements: 3.2, 3.3_

- [x] 2.3 Backend のビルドおよび起動確認
  - docker compose で backend サービスをビルド
  - Python 3.14 ランタイム上での起動を確認
  - healthcheck エンドポイント（/health）の動作確認
  - C 拡張を含む依存関係のビルド可否を確認
  - _Requirements: 3.1, 3.2, 3.4, 6.1, 6.2_

- [x] 2.4 Backend テストスイートの実行
  - docker compose exec backend pytest でテストを実行
  - 全既存テストがパスすることを確認
  - テスト失敗時のログ出力を確認
  - _Requirements: 5.1, 6.1, 6.3_

### 3. Frontend の Node.js 22 / Next.js 15 / React 19 互換化

- [x] 3.1 (P) Frontend Dockerfile を Node.js 22 に更新
  - 全ステージ（deps, builder, runner）のベースイメージを `node:22.12.0-alpine` に変更（パッチレベル固定）
  - マルチステージビルド構成を維持
  - standalone 出力の生成を確認
  - _Requirements: 4.1, 4.4, 6.1_

- [x] 3.2 (P) Frontend 依存関係を Next.js 15 / React 19 に更新
  - **package.json の依存関係を更新**:
    - `next`: **15.1.11 以降**（15.1.11 or later）
      - **重要**: CVE-2025-55184 の最初のパッチ（15.1.3）は不完全であり、**CVE-2025-67779 に完全対処するためには 15.1.11 以降が必須**
    - `react`: 19.0.0
    - `react-dom`: 19.0.0
  - **devDependencies の型定義を更新**:
    - `@types/react`: 19.0.0
    - `@types/react-dom`: 19.0.0
  - **バージョン固定ルール**:
    - `^` プレフィックスを除去し、厳密バージョン（`package==x.y.z`）で完全固定
    - 例: `"next": "15.1.11"`（`"next": "^15.1.11"` は NG）
  - **package-lock.json の再生成とコミット**:
    - 依存関係更新後に `npm install` を実行し、package-lock.json を再生成
    - 生成された package-lock.json を必ずコミット（推移的依存のロックファイル）
  - **検証ステップ**:
    - 依存関係更新後、`npx fix-react2shell-next` を実行してバリデーション
    - このツールは React 19 と Next.js 15 の互換性問題を自動検出・修正
  - **CVE 修正の背景**:
    - **CVE-2025-55183/55184**: Next.js 15.1.3 で初回パッチリリース
    - **CVE-2025-67779**: 15.1.3 のパッチが不完全であり、**15.1.11 で完全修正**
    - 15.1.3 未満のバージョンは App Router DoS および Server Actions source leakage の脆弱性を含む
  - **セキュリティテストの実施**:
    - [ ] **App Router DoS exploit checks**: App Router の `/app/*` ルートに対する大量リクエスト送信テスト（429 Rate Limit が正常に機能することを確認）
    - [ ] **Server Actions source leakage tests**: Server Actions のソースコード漏洩検証（`"use server"` ディレクティブを含むアクションがクライアントに露出していないことを確認）
    - [ ] **CI SCA (Software Composition Analysis) scan**: CI パイプラインで npm audit および Snyk/Trivy 等の SCA ツールを実行し、既知の脆弱性がないことを確認
      - 実行例: `npm audit --audit-level=high && npx snyk test --severity-threshold=high`
  - _Requirements: 4.2_

- [x] 3.3 Next.js 15 の破壊的変更に対応
  - **公式 codemod の実行**:
    - コマンド: `npx @next/codemod@canary upgrade latest`
    - 実行環境: ローカル開発環境（DevContainer 内または開発マシン上）
  - **codemod 失敗時の対処手順**:
    - **ネットワーク確認**: npx がパッケージをダウンロードできない場合、プロキシ設定やファイアウォールを確認
    - **package.json の dev スクリプト確認**: codemod が `npm run dev` を参照する場合があるため、`"dev": "next dev"` が存在することを確認
    - **ターミナル環境の確保**: headless CI 環境（TTY なし）では codemod が対話的プロンプトで失敗する可能性があるため、**ローカル環境で実行**し、結果を PR にコミット
    - エラーログを確認し、`--dry-run` オプションで事前検証可能
  - **型エラーの手動修正ステップ**:
    - **検索**: codebase 内で以下のパターンを検索
      - `@next/codemod-error`: codemod が自動修正できなかった箇所にコメントとして挿入される
      - `UnsafeUnwrapped`: codemod が型安全性を保証できない箇所に挿入される型キャスト
    - **修正**: 各箇所を個別にレビューし、型定義を正しく適用
      - 例: `const data = result as UnsafeUnwrapped<typeof result>` → 正しい型アノテーションに置換
    - **ビルド確認**: `npm run build` を実行し、TypeScript エラーがゼロになるまで繰り返し修正
  - **async params/API の修正（該当箇所がある場合）**:
    - Next.js 15 では以下の API が非同期化され、**await が必須**:
      - `cookies()`: `const cookieStore = await cookies()`
      - `headers()`: `const headersList = await headers()`
      - `params`: Server Component/Route Handler で `async function Page({ params }) { const { id } = await params; }`
      - `searchParams`: Server Component で `async function Page({ searchParams }) { const query = await searchParams; }`
    - **修正方法**:
      - 関数を `async` に変更
      - 各 API 呼び出しに `await` を追加
      - 型定義を `Promise<...>` に更新
    - **検索コマンド**: `rg "cookies\(\)|headers\(\)|params|searchParams" --type tsx --type ts` で該当箇所を特定
  - **useFormState → useActionState の移行（使用している場合のみ）**:
    - codebase で `useFormState` を検索: `rg "useFormState" --type tsx --type ts`
    - 使用している場合、以下の変更を適用:
      - `import { useFormState } from "react-dom"` → `import { useActionState } from "react"`
      - `useFormState(action, initialState)` → `useActionState(action, initialState)`
    - 使用していない場合、このステップはスキップ
  - **codemod 後の検証チェックリスト**:
    - [ ] **ローカルビルド成功**: `npm run build` を実行し、exit code 0 で完了することを確認
    - [ ] **codemod コメント削除**: `@next/codemod-error` および `UnsafeUnwrapped` が残っていないことを確認（`rg "@next/codemod-error|UnsafeUnwrapped"`）
    - [ ] **型チェック成功**: `npm run type-check` または `npx tsc --noEmit` を実行し、TypeScript エラーがゼロであることを確認
    - [ ] **開発サーバー起動確認**: `npm run dev` を実行し、正常に起動することを確認
    - [ ] **主要ページのレンダリング確認**: ブラウザで主要ルート（`/`, `/login`, `/dashboard` 等）にアクセスし、エラーなくレンダリングされることを確認
  - _Requirements: 4.2, 4.3_

- [x] 3.4 Frontend のビルドおよび起動確認
  - docker compose で frontend サービスをビルド
  - Node.js 22 ランタイム上での起動を確認
  - healthcheck の動作確認
  - ビルド失敗時のログ出力を確認
  - _Requirements: 4.1, 4.2, 4.4, 6.1_

- [x] 3.5 Frontend テストスイートの実行
  - docker compose exec frontend npm test でユニットテストを実行
  - 全既存テストがパスすることを確認
  - テスト失敗時のログ出力を確認
  - _Requirements: 5.2, 6.1, 6.3_

### 4. テスト実行スクリプトの整備

- [x] 4.1 (P) テスト実行スクリプトを作成
  - **スクリプト仕様**:
    - **ファイル名**: `scripts/run-tests.sh`
    - **実行権限**: `chmod +x scripts/run-tests.sh` で実行可能にする
    - **Shebang**: `#!/usr/bin/env bash` を使用し、ポータビリティを確保
    - **実行環境**: ホスト、DevContainer 内、CI/CD パイプラインのいずれでも実行可能
  - **サポートするテストモード**:
    - `backend`: Backend テスト（pytest）のみ実行
    - `frontend`: Frontend ユニットテスト（Jest）のみ実行
    - `e2e`: E2E テスト（Playwright）のみ実行
    - `all`: 全テスト（backend + frontend + e2e）を順次実行
  - **実行例と詳細動作**:
    - **Backend テストモード**:
      ```bash
      ./scripts/run-tests.sh backend
      # 実行コマンド: docker compose exec -T backend pytest --json-report --json-report-file=/tmp/pytest-results.json --cov --cov-report=json:/tmp/coverage.json --junit-xml=/tmp/junit.xml
      # 出力: pytest の標準出力（テスト名、結果、実行時間）
      # アーティファクト: /tmp/pytest-results.json, /tmp/coverage.json, /tmp/junit.xml
      ```
    - **Frontend テストモード**:
      ```bash
      ./scripts/run-tests.sh frontend
      # 実行コマンド: docker compose exec -T frontend npm test -- --json --outputFile=/tmp/jest-results.json --coverage --coverageReporters=json --reporters=default --reporters=jest-junit
      # 出力: Jest の標準出力（テストスイート名、結果、カバレッジサマリー）
      # アーティファクト: /tmp/jest-results.json, /tmp/coverage/coverage-final.json, /tmp/junit.xml
      ```
    - **E2E テストモード**:
      ```bash
      ./scripts/run-tests.sh e2e
      # 実行コマンド: docker compose exec -T frontend npm run test:e2e -- --reporter=json --reporter=junit --output-file=/tmp/playwright-results.json
      # 出力: Playwright の標準出力（テストケース名、結果、スクリーンショット URL）
      # アーティファクト: /tmp/playwright-results.json, /tmp/junit.xml, /tmp/test-results/ (スクリーンショット/動画)
      ```
    - **All テストモード**:
      ```bash
      ./scripts/run-tests.sh all
      # 実行順序: backend → frontend → e2e（早期終了: いずれかが失敗した場合、後続テストをスキップし即座に終了）
      # 出力: 各テストモードの標準出力を順次表示
      # アーティファクト: 全テストモードのアーティファクトを /tmp/ に保存
      ```
  - **戻り値（Exit Code）の定義**:
    - **0**: 全テストが成功（テスト実行が完了し、失敗なし）
    - **1**: テスト失敗（1つ以上のテストケースが失敗）
    - **2**: スクリプト引数エラー（不正なテストモード指定、例: `./run-tests.sh invalid`）
    - **3**: Docker Compose サービスが起動していない（`docker compose ps` でサービスが見つからない）
    - **4**: タイムアウト（テスト実行が指定時間内に完了しなかった）
    - **使用例**:
      ```bash
      ./scripts/run-tests.sh backend
      echo $?  # 0=成功、1=失敗、2=引数エラー、3=サービス未起動、4=タイムアウト
      ```
  - **COMPOSE_FILE 環境変数のサポート**:
    - **デフォルト値**: 未指定の場合、`docker-compose.yml` を使用
    - **優先順位**:
      1. `COMPOSE_FILE` 環境変数が設定されている場合、その値を使用（例: `COMPOSE_FILE=docker-compose.devcontainer.yml ./run-tests.sh all`）
      2. 複数ファイル指定時（コロン区切り）は、右側が優先（例: `COMPOSE_FILE=docker-compose.yml:docker-compose.override.yml` では override.yml の設定が優先）
      3. 環境変数未設定の場合、スクリプトは `docker-compose.yml` をデフォルト値として使用
    - **検証**: スクリプト内で以下のロジックを実装
      ```bash
      COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.yml}
      # 指定されたファイルが存在するか確認
      for file in ${COMPOSE_FILE//:/ }; do
        if [ ! -f "$file" ]; then
          echo "ERROR: Compose file not found: $file" >&2
          exit 3
        fi
      done
      ```
  - **タイムアウト設定**:
    - **デフォルトタイムアウト**:
      - backend: 300秒（5分）
      - frontend: 180秒（3分）
      - e2e: 600秒（10分）
      - all: 1200秒（各ステージに適用）
    - **環境変数でのオーバーライド**:
      ```bash
      TEST_TIMEOUT=900 ./scripts/run-tests.sh e2e  # E2E テストのタイムアウトを15分に延長
      ```
    - **タイムアウト実装**: `timeout` コマンドを使用
      ```bash
      timeout ${TEST_TIMEOUT:-600} docker compose exec -T frontend npm run test:e2e || {
        exit_code=$?
        if [ $exit_code -eq 124 ]; then
          echo "ERROR: Test timed out after ${TEST_TIMEOUT:-600} seconds" >&2
          exit 4
        fi
        exit $exit_code
      }
      ```
    - **cc-sdd との整合性**: cc-sdd（Claude Code Spec-Driven Development）からの呼び出し時、外部タイムアウトが設定されている場合、スクリプトの内部タイムアウトはそれより短く設定する（外部タイムアウトの80%を推奨）
  - **出力形式の機械可読対応**:
    - **JSON 出力**:
      - Backend: pytest-json-report により `/tmp/pytest-results.json` に出力
      - Frontend: Jest の `--json` フラグにより `/tmp/jest-results.json` に出力
      - E2E: Playwright の `--reporter=json` により `/tmp/playwright-results.json` に出力
    - **XML 出力（JUnit 形式）**:
      - Backend: pytest の `--junit-xml` により `/tmp/junit.xml` に出力
      - Frontend: jest-junit により `/tmp/junit.xml` に出力
      - E2E: Playwright の `--reporter=junit` により `/tmp/junit.xml` に出力
    - **CI/CD 統合**: GitLab CI の `artifacts:reports:junit` または GitHub Actions の `junit-report` アクションで XML を自動解析
    - **カバレッジレポート**:
      - Backend: coverage.py により `/tmp/coverage.json` に出力
      - Frontend: Jest の coverage-json レポーターにより `/tmp/coverage/coverage-final.json` に出力
    - **出力例（JSON）**:
      ```json
      {
        "summary": {
          "total": 150,
          "passed": 148,
          "failed": 2,
          "skipped": 0,
          "duration": 120.5
        },
        "tests": [
          {
            "name": "test_backend.py::test_example",
            "outcome": "passed",
            "duration": 0.5
          }
        ]
      }
      ```
  - **CI/CD 環境での実行**:
    - **TTY なし**: `-T` フラグを使用し、`docker compose exec` を TTY なしで実行
    - **並列実行サポート**: スクリプトはステートレスであり、複数のテストモードを並列実行可能（ただし、推奨は順次実行）
    - **環境変数の検出**: `CI` 環境変数が設定されている場合、CI モードとして動作（カラー出力を無効化、詳細ログを有効化）
  - **エラーハンドリング**:
    - **サービス未起動の検出**: テスト実行前に `docker compose ps` でサービス状態を確認
      ```bash
      if ! docker compose ps backend | grep -q "Up"; then
        echo "ERROR: Backend service is not running. Start with: docker compose up -d" >&2
        exit 3
      fi
      ```
    - **Docker 未インストール**: `docker` コマンドが存在しない場合、明確なエラーメッセージを表示
      ```bash
      if ! command -v docker &> /dev/null; then
        echo "ERROR: Docker is not installed or not in PATH" >&2
        exit 3
      fi
      ```
  - **実装チェックリスト**:
    - [ ] スクリプトが `scripts/run-tests.sh` に配置され、実行可能である（`chmod +x`）
    - [ ] 4つのテストモード（backend, frontend, e2e, all）がサポートされている
    - [ ] 戻り値が定義通り（0=成功、1=失敗、2=引数エラー、3=サービス未起動、4=タイムアウト）である
    - [ ] `COMPOSE_FILE` 環境変数がサポートされ、優先順位が実装されている
    - [ ] タイムアウトがデフォルト値で設定され、`TEST_TIMEOUT` 環境変数でオーバーライド可能である
    - [ ] JSON および JUnit XML 形式の出力が生成される
    - [ ] CI/CD 環境（`-T` フラグ、`CI` 環境変数検出）がサポートされている
    - [ ] エラーハンドリング（サービス未起動、Docker 未インストール）が実装されている
  - _Requirements: 2.1, 2.2, 2.3, 1.4_

- [x] 4.2 E2E テストの実行確認
  - **Playwright Docker 環境の前提条件**:
    - **Dockerイメージタグ**: プロジェクトの Playwright バージョンに合致した公式イメージを使用
      - 確認方法: `jq -r '.devDependencies.["@playwright/test"]' frontend/package.json` で Playwright バージョンを取得
      - イメージ例: `mcr.microsoft.com/playwright:v1.48.2-jammy`（バージョンは package.json に合わせる）
    - **ブラウザダウンロード設定**: Dockerfile または CI で `npx playwright install --with-deps chromium` を実行し、Chromium をプリインストール
    - **Chromium 用共有メモリ**:
      - docker-compose.devcontainer.yml または docker-compose.yml の frontend サービスに `shm_size: 1gb` を追加
      - docker run で実行する場合: `docker run --shm-size=1gb ...`
      - 理由: Chromium が /dev/shm を大量に使用するため、デフォルト（64MB）では不足しクラッシュする
  - **playwright.config.ts の設定**:
    - **viewport 寸法の明示**: デフォルト値に依存せず、明示的に指定
      ```typescript
      use: {
        viewport: { width: 1280, height: 720 },
      }
      ```
    - **headless モード**: CI/CD および DevContainer での実行のため `headless: true` を設定
      ```typescript
      use: {
        headless: true,
      }
      ```
    - **Linux CI で headless を使わない場合**: Xvfb（X Virtual Framebuffer）をインストールし、以下のように実行
      ```bash
      # Xvfb インストール（Dockerfile）
      apt-get install -y xvfb
      # テスト実行時
      xvfb-run -a npm run test:e2e
      ```
      ただし、通常は `headless: true` を推奨
    - **trace 設定**: デバッグ用に trace を有効化
      ```typescript
      use: {
        trace: 'on-first-retry',
      }
      ```
    - **設定のコミット**: これらの設定を playwright.config.ts に反映し、リポジトリにコミット
  - **Docker 要件のドキュメント化**:
    - docker-compose.devcontainer.yml の frontend サービスに以下のコメントを追加:
      ```yaml
      frontend:
        shm_size: 1gb  # Chromium requires at least 1GB shared memory for E2E tests
      ```
    - または README.md に以下のセクションを追加:
      ```markdown
      ## E2E Testing Requirements
      - Playwright requires Docker with `--shm-size=1gb` for Chromium
      - Ensure `shm_size: 1gb` is set in docker-compose.yml or use `docker run --shm-size=1gb`
      ```
  - **E2E テストの実行**:
    - コマンド: `docker compose exec frontend npm run test:e2e`
    - 実行環境: DevContainer 内または CI パイプライン
  - **主要ユーザーフローの具体的テストステップ**:
    - **ログイン**:
      - テストケース: ログインページ（`/login`）にアクセス
      - 入力: ユーザー名 `testuser`、パスワード `testpass123` を入力
      - 検証: ログイン成功後、ダッシュボード（`/dashboard`）にリダイレクトされることを確認
      - 検証: ダッシュボードに "Welcome, testuser" が表示されることを確認
    - **コンテナ操作**:
      - テストケース: ダッシュボードから "Containers" ページ（`/containers`）に移動
      - 操作: 新規コンテナ作成ボタンをクリック
      - 入力: コンテナ名 `test-nginx`、イメージ `nginx:latest` を入力
      - 操作: "Create" ボタンをクリック
      - 検証: コンテナリストに `test-nginx` が表示され、ステータスが "Running" であることを確認
      - クリーンアップ: テスト終了後、コンテナを削除
    - **カタログ閲覧**:
      - テストケース: ヘッダーメニューから "Catalog" ページ（`/catalog`）に移動
      - 検証: カタログページが正常にレンダリングされることを確認
      - 検証: 少なくとも3つのカタログアイテム（例: `nginx`, `postgres`, `redis`）が表示されることを確認
      - 操作: カタログアイテム `nginx` をクリック
      - 検証: 詳細ページ（`/catalog/nginx`）にリダイレクトされ、イメージ説明が表示されることを確認
  - **Playwright 実行環境の検証**:
    - [x] Chromium ブラウザがインストールされている（`npx playwright install --dry-run chromium` が成功）
    - [x] `shm_size: 1gb` が docker-compose に設定されている
    - [x] playwright.config.ts に `headless: true`, `viewport: { width: 1280, height: 720 }`, `trace: 'on-first-retry'` が設定されている
  - _Requirements: 5.3, 6.3_

- [x] 4.3 テストスクリプトの動作確認
  - ホストから scripts/run-tests.sh all を実行し、全テストがパスすることを確認
  - workspace コンテナから scripts/run-tests.sh all を実行し、同様に確認
  - cc-sdd からの呼び出しインターフェースを検証
  - _Requirements: 2.1, 2.2, 2.3, 6.3_

### 5. 統合検証とドキュメント更新

- [x] 5.1 統合テストの実行
  - **Backend API の起動確認（healthcheck）**:
    - コマンド: `curl -f http://localhost:8000/health || exit 1`
    - 検証: HTTP 200 が返され、レスポンスに `{"status": "ok"}` が含まれることを確認
  - **Frontend の Backend API 接続確認**:
    - コマンド: `docker compose exec frontend curl -f http://backend:8000/api/v1/status || exit 1`
    - 検証: Frontend コンテナから Backend コンテナへの通信が成功することを確認
  - **Docker ソケットアクセスの動作確認（rootless Docker 環境を含む）**:
    - **タスク 1.3 との依存関係**: **タスク 1.3 で設定したソケットマウント構成が適用され、正常に機能していることを確認**
    - **動的 UID 評価の使用**: ハードコードされた `$UID` ではなく、`$(id -u)` を使用してポータビリティを確保
      - 例: `/run/user/$(id -u)/docker.sock` を使用
    - **rootless Docker テストステップ**:
      1. **DevContainer へのアクセス**: `docker compose -f docker-compose.devcontainer.yml exec workspace bash` でコンテナに入る
      2. **ソケットパスの確認**:
         ```bash
         # rootless ソケットの確認
         if [ -S "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/docker.sock" ]; then
           echo "Rootless socket found: ${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/docker.sock"
         # rootful ソケットの確認
         elif [ -S "/var/run/docker.sock" ]; then
           echo "Rootful socket found: /var/run/docker.sock"
         else
           echo "ERROR: No Docker socket found"
           exit 1
         fi
         ```
      3. **グループメンバーシップの検証**:
         - rootful Docker: `groups | grep -q docker && echo "User is in docker group" || echo "ERROR: User not in docker group"`
         - rootless Docker: `whoami` の出力が dockerd を実行しているユーザーと一致することを確認
      4. **Docker コマンド実行テスト**:
         ```bash
         docker ps  # コンテナリストが表示されることを確認
         docker version  # Docker クライアント/サーバーバージョンが表示されることを確認
         ```
      5. **ソケット所有権/パーミッションの確認**:
         ```bash
         ls -la /var/run/docker.sock  # rootful の場合
         # 出力例: srw-rw---- 1 root docker 0 Jan 18 12:00 /var/run/docker.sock
         ls -la "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/docker.sock"  # rootless の場合
         # 出力例: srw------- 1 user user 0 Jan 18 12:00 /run/user/1000/docker.sock
         ```
    - **トラブルシューティング手順（ソケット権限エラーの場合）**:
      - **ソケット所有権/パーミッションの検査**:
        ```bash
        # ホストで実行
        ls -la /var/run/docker.sock
        # 出力例: srw-rw---- 1 root docker 0 Jan 18 12:00 /var/run/docker.sock
        ```
      - **グループメンバーシップの調整**:
        ```bash
        # ホストでユーザーを docker グループに追加（rootful Docker）
        sudo usermod -aG docker $USER
        # 変更を適用するため、ログアウト/ログインまたは newgrp docker
        ```
      - **bind-mount モードの調整**:
        - docker-compose.yml で `:rw` モードを明示的に指定:
          ```yaml
          volumes:
            - /var/run/docker.sock:/var/run/docker.sock:rw
          ```
      - **コンテナの再起動**:
        ```bash
        docker compose -f docker-compose.devcontainer.yml down
        docker compose -f docker-compose.devcontainer.yml up -d
        ```
      - **rootless Docker 特有の問題**:
        - `XDG_RUNTIME_DIR` 環境変数が正しく設定されているか確認: `echo $XDG_RUNTIME_DIR`（通常は `/run/user/$(id -u)`）
        - rootless dockerd が起動しているか確認: `systemctl --user status docker`
  - **DevContainer 内での開発サーバー起動確認**:
    - Backend: `docker compose -f docker-compose.devcontainer.yml exec backend uvicorn app.main:app --host 0.0.0.0 --port 8000` が起動することを確認
    - Frontend: `docker compose -f docker-compose.devcontainer.yml exec frontend npm run dev` が起動し、http://localhost:3000 にアクセス可能であることを確認
  - _Requirements: 1.4, 2.4, 6.3_

- [x] 5.2 回帰テストの実行
  - **ベースライン取得（技術スタック更新前）**:
    - **実行タイミング**: 技術スタック更新を開始する直前、現在の main ブランチで実行
    - **テストスイート実行コマンド**:
      ```bash
      # Backend テスト（pytest）
      docker compose exec backend pytest --json-report --json-report-file=/tmp/pytest-baseline.json --cov --cov-report=json:/tmp/coverage-backend-baseline.json --durations=0
      # Frontend テスト（Jest）
      docker compose exec frontend npm test -- --json --outputFile=/tmp/jest-baseline.json --coverage --coverageReporters=json
      # E2E テスト（Playwright）
      docker compose exec frontend npm run test:e2e -- --reporter=json --output=/tmp/playwright-baseline.json
      ```
    - **アーティファクト保存**:
      - **テスト結果 JSON**:
        - Backend: `artifacts/baseline/pytest-results-YYYYMMDD-HHMMSS.json`
        - Frontend: `artifacts/baseline/jest-results-YYYYMMDD-HHMMSS.json`
        - E2E: `artifacts/baseline/playwright-results-YYYYMMDD-HHMMSS.json`
      - **カバレッジレポート**:
        - Backend: `artifacts/baseline/coverage-backend-YYYYMMDD-HHMMSS.json`
        - Frontend: `artifacts/baseline/coverage-frontend-YYYYMMDD-HHMMSS.json`
      - **タイミング情報**: 各テスト結果 JSON に含まれる `duration` フィールド
      - **タイムスタンプ**: ファイル名に ISO 8601 形式（例: `20250118-143000`）で記録
    - **CI アーティファクト**: GitLab CI/GitHub Actions の artifacts 機能で保存し、後続ジョブで参照可能にする
  - **技術スタック更新後のテスト実行**:
    - 上記と同じコマンドを実行し、結果を `artifacts/updated/` ディレクトリに保存
  - **比較メトリクス**:
    - **テスト実行統計**:
      - 実行テスト総数（total tests run）
      - 成功数（passes）
      - 失敗数（failures）
      - スキップ数（skipped）
      - flaky テスト数（flaky tests: 複数回実行で成功/失敗が変動するテスト）
    - **パフォーマンスメトリクス**:
      - テストごとのランタイム（per-test runtime in seconds）
      - 総実行時間（total execution time）
      - 実行時間の上位10スロウテスト（top 10 slowest tests）
    - **カバレッジメトリクス**:
      - グローバルカバレッジ%（global coverage %）
      - ファイル単位カバレッジ%（per-file coverage %）
      - 関数/行カバレッジ（function/line coverage）
  - **受入しきい値**:
    - **実行時間**: ±10% の範囲内（例: ベースライン 100秒なら 90-110秒が許容範囲）
    - **新規失敗テスト**: flaky マークがない限り、新規失敗テストは不可（0件）
    - **カバレッジ低下**:
      - グローバル: ≤0.5%（例: 85.0% → 84.5% までは許容）
      - クリティカルモジュール（例: backend/app/core/, frontend/src/components/）: ≤1.0% の低下まで許容
    - **flaky テスト**: 新規 flaky テストは3件以下（既存 flaky は count に含めない）
  - **比較方法とツール**:
    - **CI アーティファクトの取得**: GitLab CI の `artifacts:reports:junit` または GitHub Actions の `upload-artifact` で保存されたベースライン結果を取得
    - **比較スクリプト**: `scripts/compare-test-results.py` を作成し、以下を実装:
      ```python
      # 疑似コード
      import json
      baseline = load_json("artifacts/baseline/pytest-results-*.json")
      updated = load_json("artifacts/updated/pytest-results-*.json")

      # テストごとのステータス変更を抽出
      status_changes = diff_test_status(baseline, updated)
      # ランタイムデルタを計算
      runtime_deltas = diff_runtime(baseline, updated)
      # カバレッジ diff を計算
      coverage_diff = diff_coverage("artifacts/baseline/coverage-*.json", "artifacts/updated/coverage-*.json")

      # レポート生成
      generate_report(status_changes, runtime_deltas, coverage_diff)
      ```
    - **既存レポーターの活用**: pytest-json-report, jest-junit, playwright-html-reporter 等の出力形式を利用
  - **レポート出力**:
    - **機械可読サマリー（JSON）**: `artifacts/comparison/regression-summary.json`
      ```json
      {
        "baseline_timestamp": "2025-01-18T14:30:00Z",
        "updated_timestamp": "2025-01-19T10:15:00Z",
        "total_tests": { "baseline": 150, "updated": 150 },
        "passes": { "baseline": 148, "updated": 149 },
        "failures": { "baseline": 2, "updated": 1 },
        "new_failures": [],
        "resolved_failures": ["test_backend.py::test_example"],
        "flaky_tests": ["test_frontend.jsx::test_flaky_component"],
        "execution_time": {
          "baseline": 120.5,
          "updated": 118.2,
          "delta_percent": -1.9
        },
        "coverage": {
          "baseline_global": 85.0,
          "updated_global": 84.8,
          "delta_percent": -0.2,
          "per_module": {
            "backend/app/core": { "baseline": 90.0, "updated": 89.5, "delta": -0.5 }
          }
        },
        "acceptance": {
          "execution_time_within_threshold": true,
          "no_new_failures": true,
          "coverage_within_threshold": true,
          "overall_pass": true
        }
      }
      ```
    - **人間向けレポート（HTML/Markdown）**: `artifacts/comparison/regression-report.html` または `regression-report.md`
      - **セクション構成**:
        1. **サマリー**: 全体的な Pass/Fail、主要メトリクスの表
        2. **リグレッション**: 新規失敗テスト一覧とログへのリンク
        3. **Flaky テスト**: flaky と判定されたテスト一覧
        4. **メトリクスデルタ**: 実行時間、カバレッジの変化をグラフ/表で表示
        5. **カバレッジ詳細**: ファイル単位のカバレッジ変化（特に低下が大きいファイルをハイライト）
        6. **スロウテスト**: 実行時間上位10テストの比較
      - **リンク**: 失敗テストのログファイル（`artifacts/updated/logs/test-backend-failure.log`）へのリンク
  - **実装チェックリスト**:
    - [ ] ベースライン取得スクリプトが実装されている（`scripts/capture-baseline.sh`）
    - [ ] ベースラインアーティファクトが指定パス（`artifacts/baseline/`）に保存されている
    - [ ] 比較スクリプト（`scripts/compare-test-results.py`）が実装され、全メトリクスを計算できる
    - [ ] 受入しきい値が比較スクリプトにハードコードまたは設定ファイル（`scripts/regression-thresholds.json`）で定義されている
    - [ ] 機械可読サマリー（`regression-summary.json`）が出力される
    - [ ] 人間向けレポート（HTML/Markdown）が出力され、リグレッション/flaky/メトリクスデルタがハイライトされている
    - [ ] CI パイプライン（`.gitlab-ci.yml` または `.github/workflows/regression.yml`）にベースライン取得と比較ジョブが追加されている
    - [ ] レポートが CI アーティファクトとしてダウンロード可能である
  - _Requirements: 5.1, 5.2, 5.3, 6.3_

- [x] 5.3 バージョン固定の最終確認
  - Python 3.14.x / Node.js 22.12.x / Next.js 15.1.x の最新パッチバージョンを確認
  - 実装開始時点で実在し、CVE 修正を満たすバージョンに確定
  - requirements.txt と package-lock.json のコミットを確認
  - _Requirements: 3.2, 4.2, 6.3_

- [x] 5.4 ドキュメント更新
  - **DevContainer セットアップ手順のドキュメント化**:
    - **ドキュメント配置**: README.md または `.devcontainer/README.md` に以下のセクションを追加
    - **セクション構成**:
      1. **DevContainer 環境の概要**:
         - Python 3.14, Node.js 22, Next.js 15, React 19 の統合開発環境
         - VS Code Dev Containers 拡張機能による一貫した開発環境の提供
      2. **前提条件**:
         - Docker Desktop（または Docker Engine + Docker Compose）がインストールされていること
         - VS Code がインストールされていること
         - VS Code Dev Containers 拡張機能（`ms-vscode-remote.remote-containers`）がインストールされていること
      3. **セットアップ手順**:
         ```markdown
         1. リポジトリをクローン:
            ```bash
            git clone https://github.com/your-org/docker-mcp-gateway-web-console.git
            cd docker-mcp-gateway-web-console
            ```
         2. VS Code でプロジェクトを開く:
            ```bash
            code .
            ```
         3. コマンドパレット（Ctrl+Shift+P / Cmd+Shift+P）を開き、"Dev Containers: Reopen in Container" を選択
         4. DevContainer が起動し、依存関係が自動的にインストールされる（postCreateCommand により Backend/Frontend の依存関係がインストールされる）
         5. ターミナルで開発サーバーを起動:
            - Backend: `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
            - Frontend: `cd frontend && npm run dev`
         ```
      4. **利用可能なサービス**:
         - Backend API: http://localhost:8000
         - Frontend: http://localhost:3000
         - Backend API ドキュメント（Swagger UI）: http://localhost:8000/docs
  - **docker-compose.yml の変更点のドキュメント化**:
    - **ドキュメント配置**: README.md の "Infrastructure Changes" セクション、または CHANGELOG.md
    - **変更点の記載内容**:
      - **docker-compose.devcontainer.yml の追加**:
        - DevContainer 専用の Compose ファイル
        - workspace サービス（開発統合環境）の定義
        - Docker ソケットマウント（rootless/rootful 両対応）の自動検出機能
      - **Backend サービスの変更**:
        - Python 3.14.0 ベースイメージへの更新
        - マルチステージビルドの導入（builder + runtime ステージ）
        - Dockerfile.dev の追加（開発専用イメージ）
      - **Frontend サービスの変更**:
        - Node.js 22.12.0 ベースイメージへの更新
        - Next.js 15.1.11 への更新（CVE-2025-67779 対応）
        - E2E テスト用 Chromium 共有メモリ（`shm_size: 1gb`）の設定
      - **ポートフォワーディング**:
        - Backend: 8000
        - Frontend: 3000
  - **テスト実行方法のドキュメント化**:
    - **ドキュメント配置**: README.md の "Testing" セクション
    - **scripts/run-tests.sh の使用方法**:
      ```markdown
      ## テスト実行方法

      プロジェクトでは `scripts/run-tests.sh` を使用して、Backend/Frontend/E2E テストを統一的に実行できます。

      ### ローカルでのテスト実行

      ```bash
      # 全テストを実行
      ./scripts/run-tests.sh all

      # Backend テストのみ
      ./scripts/run-tests.sh backend

      # Frontend テストのみ
      ./scripts/run-tests.sh frontend

      # E2E テストのみ
      ./scripts/run-tests.sh e2e
      ```

      ### DevContainer 内でのテスト実行

      DevContainer 内でも同様のコマンドが使用可能です:

      ```bash
      # DevContainer 内のターミナルで
      ./scripts/run-tests.sh all
      ```

      ### CI/CD でのテスト実行

      GitLab CI または GitHub Actions でのテスト実行は、以下のように設定します:

      **GitLab CI (.gitlab-ci.yml)**:
      ```yaml
      test:
        stage: test
        image: docker:latest
        services:
          - docker:dind
        script:
          - docker compose up -d
          - docker compose exec -T backend pytest
          - docker compose exec -T frontend npm test
          - docker compose exec -T frontend npm run test:e2e
        artifacts:
          reports:
            junit: artifacts/test-results/*.xml
      ```

      **GitHub Actions (.github/workflows/test.yml)**:
      ```yaml
      name: Test
      on: [push, pull_request]
      jobs:
        test:
          runs-on: ubuntu-latest
          steps:
            - uses: actions/checkout@v4
            - name: Run tests
              run: |
                docker compose up -d
                ./scripts/run-tests.sh all
            - name: Upload test results
              uses: actions/upload-artifact@v4
              with:
                name: test-results
                path: artifacts/
      ```
      ```
  - **既知の制限事項とトラブルシューティングのドキュメント化**:
    - **ドキュメント配置**: README.md の "Troubleshooting" セクション、または `.devcontainer/TROUBLESHOOTING.md`
    - **既知の制限事項**:
      - **Docker Desktop on macOS/Windows**: ファイルシステムパフォーマンスが Linux ネイティブに比べて低下する可能性あり（特にnpm installやpip install時）
      - **rootless Docker**: 一部のホスト環境で Docker ソケットパスの自動検出が失敗する場合あり
      - **メモリ制約**: E2E テスト（Playwright）は最低 4GB の Docker メモリ割り当てが推奨
    - **トラブルシューティング**:
      - **問題: DevContainer が起動しない**
        - 解決策: Docker が起動しているか確認（`docker ps`）、VS Code を再起動、`docker compose down` で既存コンテナをクリーンアップ
      - **問題: Docker ソケットアクセスエラー（"permission denied"）**
        - 解決策: ユーザーを docker グループに追加（`sudo usermod -aG docker $USER`）、ログアウト/ログイン、rootless Docker の場合は `systemctl --user status docker` でサービス状態を確認
      - **問題: E2E テストが "Out of memory" で失敗**
        - 解決策: docker-compose.yml で `shm_size: 1gb` が設定されているか確認、Docker Desktop のメモリ割り当てを増やす（Settings → Resources → Memory）
      - **問題: Backend/Frontend の依存関係インストールが遅い**
        - 解決策: Docker Compose のビルドキャッシュを活用（`docker compose build --no-cache` で再ビルド）、pip/npm キャッシュボリュームを使用
      - **問題: ポートが既に使用されている（"port is already allocated"）**
        - 解決策: 既存のサービスを停止（`lsof -i :8000` でプロセスを特定し `kill`）、または docker-compose.yml のポート番号を変更
  - **実装チェックリスト**:
    - [x] README.md または `.devcontainer/README.md` に DevContainer セットアップ手順が記載されている
    - [x] docker-compose.yml の変更点が README.md または CHANGELOG.md に記載されている
    - [x] scripts/run-tests.sh の使用方法が README.md の "Testing" セクションに記載されている
    - [x] CI/CD 統合ステップ（GitLab CI/GitHub Actions の設定例）がドキュメント化されている
    - [x] 既知の制限事項が5つ以上リストされている
    - [x] トラブルシューティングガイドが5つ以上のシナリオをカバーしている
  - _Requirements: 1.2, 1.4, 2.3, 4.1, 4.2, 5.1_

---

## 要件カバレッジ

| 要件 | カバーするタスク |
|------|-----------------|
| 1.1 | 1.1, 1.3, 1.4 |
| 1.2 | 1.2, 1.3, 1.4, 5.4 |
| 1.3 | 1.2, 1.4 |
| 1.4 | 1.1, 1.2, 1.3, 1.4, 4.1, 5.1, 5.4 |
| 2.1 | 4.1, 4.3 |
| 2.2 | 4.1, 4.3 |
| 2.3 | 4.1, 4.3, 5.4 |
| 2.4 | 1.3, 5.1 |
| 3.1 | 2.1, 2.3 |
| 3.2 | 2.2, 2.3, 5.3 |
| 3.3 | 2.2 |
| 3.4 | 2.1, 2.3 |
| 4.1 | 3.1, 3.4, 5.4 |
| 4.2 | 3.2, 3.3, 3.4, 5.3, 5.4 |
| 4.3 | 3.3 |
| 4.4 | 3.1, 3.4 |
| 5.1 | 2.4, 5.2, 5.4 |
| 5.2 | 3.5, 5.2 |
| 5.3 | 4.2, 5.2 |
| 6.1 | 2.1, 2.3, 2.4, 3.1, 3.4, 3.5 |
| 6.2 | 2.1, 2.3 |
| 6.3 | 1.2, 2.4, 3.5, 4.2, 4.3, 5.1, 5.2, 5.3 |

**全6要件（24受入基準）がカバーされています。**

---

## 実装順序の推奨

### フェーズ間依存関係（DAG）

以下は各フェーズ間の依存関係を有向非環グラフ（DAG）で表現したものです。矢印（→）は「完了後に開始可能」を示します。

```
Phase 1 (DevContainer構築)
  ├─→ Phase 2 (Backend更新)
  ├─→ Phase 2' (Frontend基盤更新)
  └─→ Phase 4 (テストスクリプト整備) ※部分的依存

Phase 2 (Backend更新) ──┐
Phase 2' (Frontend基盤) ─┤
                         ├─→ Phase 3 (Frontend移行)
Phase 4 (テストスクリプト)┘

Phase 3 (Frontend移行) ──┐
Phase 4 (テストスクリプト)┤
                         ├─→ Phase 5 (統合検証)
                         │
                         └─→ Phase 5 (ドキュメント)
```

### Phase 1: DevContainer 環境構築

**タスク**: 1.1, 1.2, 1.3, 1.4

**開始条件**: なし（プロジェクトの開始時点から実行可能）

**並列実行可能なタスク**:
- タスク 1.1, 1.2, 1.3 は並列実行可能（`(P)` マーカー付き）

**順序制約**:
```
1.1 (workspace Dockerfile) ─┐
1.2 (devcontainer.json)     ├─→ 1.4 (起動確認)
1.3 (docker-compose.yml)    ┘
```

**完了条件**:
- タスク 1.4 が完了（DevContainer が正常に起動し、Python 3.14 および Node.js 22 が実行可能）

---

### Phase 2: Backend 更新

**タスク**: 2.1, 2.2, 2.3, 2.4

**開始条件**:
- **必須**: Phase 1 の完了（特にタスク 1.4: DevContainer 環境起動確認）
- **理由**: タスク 2.3 「docker compose でbackendサービスをビルド」は機能するDevContainer環境を必要とする

**並列実行可能なタスク**:
- タスク 2.1, 2.2 は並列実行可能（`(P)` マーカー付き）
- **Phase 2' (Frontend Dockerfile/依存関係更新)** とも並列実行可能

**順序制約**:
```
2.1 (Backend Dockerfile) ─┐
2.2 (依存関係更新)        ├─→ 2.3 (ビルド確認) ─→ 2.4 (テスト実行)
1.4 (DevContainer起動)    ┘
```

**完了条件**:
- タスク 2.4 が完了（Backend テストスイートが全パス）

---

### Phase 2': Frontend 基盤更新（Phase 2 と並列実行）

**タスク**: 3.1, 3.2

**開始条件**:
- **必須**: Phase 1 の完了（特にタスク 1.4: DevContainer 環境起動確認）
- **理由**: タスク 3.1 「docker compose でfrontendサービスをビルド」は機能するDevContainer環境を必要とする

**並列実行可能なタスク**:
- タスク 3.1, 3.2 は並列実行可能（`(P)` マーカー付き）
- **Phase 2 (Backend 更新)** とも並列実行可能

**順序制約**:
```
3.1 (Frontend Dockerfile) ─┐
3.2 (依存関係更新)         ├─→ Phase 3 へ
1.4 (DevContainer起動)     ┘
```

**完了条件**:
- タスク 3.2 が完了（package.json および package-lock.json が更新され、Next.js 15.1.11 がインストール済み）

---

### Phase 3: Frontend コード移行とテスト

**タスク**: 3.3, 3.4, 3.5

**開始条件**:
- **必須**: Phase 2' の完了（タスク 3.1, 3.2）
- **必須**: Phase 4 の部分完了（タスク 4.1: テスト実行スクリプト作成）※タスク 3.5 で使用
- **理由**: タスク 3.3 は Next.js 15.1.11 がインストールされた環境でcodemodを実行する必要がある

**順序制約**:
```
3.2 (依存関係更新) ─→ 3.3 (codemod実行) ─→ 3.4 (ビルド確認) ─→ 3.5 (テスト実行)
                                                                    ↑
                                                    4.1 (テストスクリプト)
```

**完了条件**:
- タスク 3.5 が完了（Frontend テストスイートが全パス）

---

### Phase 4: テストスクリプト整備

**タスク**: 4.1, 4.2, 4.3

**開始条件**:
- **部分依存**: Phase 1 の完了（タスク 4.1 は DevContainer 環境で実行可能なスクリプトを作成）
- **理由**: タスク 4.1 は Backend/Frontend のテスト実行環境が整っている必要はないが、DevContainer 環境の理解が必要

**並列実行可能なタスク**:
- タスク 4.1 は Phase 2, Phase 2' と並列実行可能（`(P)` マーカー付き）
- ただし、タスク 4.2, 4.3 は Phase 2, Phase 3 の完了後に実行

**順序制約**:
```
1.4 (DevContainer起動) ─→ 4.1 (スクリプト作成) ─┐
                                                ├─→ 4.3 (動作確認)
2.4 (Backend テスト)    ─→ 4.2 (E2E 確認)    ─┘
3.5 (Frontend テスト)   ─┘
```

**完了条件**:
- タスク 4.3 が完了（scripts/run-tests.sh が全テストモードで正常動作）

---

### Phase 5: 統合検証とドキュメント

**タスク**: 5.1, 5.2, 5.3, 5.4

**開始条件**:
- **必須**: Phase 2, Phase 3, Phase 4 の完了
- **理由**: 統合テスト（5.1）は全コンポーネント（Backend, Frontend, DevContainer, テストスクリプト）が機能することを検証する

**順序制約**:
```
2.4 (Backend テスト)    ─┐
3.5 (Frontend テスト)   ─┤
4.3 (スクリプト動作確認)─┼─→ 5.1 (統合テスト) ─→ 5.2 (回帰テスト) ─→ 5.3 (バージョン確認)
                         │                                                  ↓
                         └─→ 5.4 (ドキュメント更新) ←───────────────────────┘
```

**完了条件**:
- タスク 5.4 が完了（README.md および関連ドキュメントが更新され、全テストが回帰確認済み）

---

### タスク依存関係マトリクス

以下は各タスクの直接依存関係を示すマトリクスです。

| タスク | 依存タスク（完了必須） | 備考 |
|--------|----------------------|------|
| 1.1 | なし | 並列実行可 (P) |
| 1.2 | なし | 並列実行可 (P) |
| 1.3 | なし | 並列実行可 (P) |
| 1.4 | 1.1, 1.2, 1.3 | Phase 1 の最終タスク |
| 2.1 | 1.4 | 並列実行可 (P) with 2.2, 3.1, 3.2 |
| 2.2 | 1.4 | 並列実行可 (P) with 2.1, 3.1, 3.2 |
| 2.3 | 2.1, 2.2 | docker compose ビルド |
| 2.4 | 2.3 | Backend テスト実行 |
| 3.1 | 1.4 | 並列実行可 (P) with 2.1, 2.2, 3.2 |
| 3.2 | 1.4 | 並列実行可 (P) with 2.1, 2.2, 3.1 |
| 3.3 | 3.2 | codemod 実行 |
| 3.4 | 3.3 | Frontend ビルド確認 |
| 3.5 | 3.4, 4.1 | Frontend テスト実行（スクリプト使用） |
| 4.1 | 1.4 | 並列実行可 (P) with Phase 2, 2' |
| 4.2 | 2.4, 3.5, 4.1 | E2E テスト確認 |
| 4.3 | 4.2 | スクリプト動作確認 |
| 5.1 | 2.4, 3.5, 4.3 | 統合テスト |
| 5.2 | 5.1 | 回帰テスト |
| 5.3 | 5.2 | バージョン固定確認 |
| 5.4 | 5.3 | ドキュメント更新 |

---

### 並列実行の最適化

以下のタスクグループは並列実行可能です（リソースが許せば）：

**グループ 1（Phase 1）**:
- 1.1, 1.2, 1.3（同時実行可能）

**グループ 2（Phase 2 & 2'）**:
- 2.1, 2.2, 3.1, 3.2（1.4 完了後に同時実行可能）

**注意事項**:
- タスク 2.3, 3.3 以降は順次実行が必要（依存関係が強い）
- Phase 4 の 4.1 は Phase 2, 2' と並列実行可能だが、4.2, 4.3 は Phase 2, 3 完了後
- Phase 5 は Phase 2, 3, 4 の完了を待つ必要がある

---

### クリティカルパス

プロジェクトの最短完了時間を決定するクリティカルパスは以下の通りです：

```
1.1/1.2/1.3 → 1.4 → 2.1/2.2 → 2.3 → 2.4 → 4.2 → 4.3 → 5.1 → 5.2 → 5.3 → 5.4
              ↓
              3.1/3.2 → 3.3 → 3.4 → 3.5 ─┘
              ↓
              4.1 ────────────────────┘
```

**推定所要時間**（各タスクが順調に進む場合）:
- Phase 1: 2-3時間（並列実行）
- Phase 2 & 2': 4-6時間（並列実行）
- Phase 3: 3-4時間（順次実行）
- Phase 4: 2-3時間（部分並列）
- Phase 5: 2-3時間（順次実行）
- **合計**: 13-19時間（実作業時間）

並列実行可能なタスクには `(P)` マーカーを付与しています。
