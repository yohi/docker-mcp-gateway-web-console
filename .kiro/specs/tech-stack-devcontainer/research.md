# Research & Design Decisions

## Summary
- **Feature**: `tech-stack-devcontainer`
- **Discovery Scope**: Extension（既存システムの技術スタック更新 + DevContainer 新規追加）
- **Key Findings**:
  - FastAPI/Pydantic は Python 3.14 をサポート済み（FastAPI PR #14165、Pydantic Issue #11613）
  - Next.js 15 では `params` と `searchParams` が非同期（Promise）に変更される破壊的変更あり
  - DevContainer は docker-compose ベースのマルチサービス構成が推奨される

## Research Log

### Python 3.14 互換性調査
- **Context**: Backend を Python 3.11 から 3.14 へ更新するための互換性確認
- **Sources Consulted**:
  - FastAPI Release Notes: [FastAPI Release Notes](https://fastapi.tiangolo.com/release-notes/)
  - Pydantic GitHub Issue #11613: [Pydantic GitHub Issue #11613](https://github.com/pydantic/pydantic/issues/11613)
  - FastAPI Docker Guide: [FastAPI Docker Guide](https://fastapi.tiangolo.com/deployment/docker/)
- **Findings**:
  - FastAPI は Python 3.14 サポートを追加済み（PR #14165）
  - Pydantic v2 は Python 3.14 サポートを進行中（PEP 649/749 対応）
  - Pydantic v1 は Python 3.14 でサポート終了のため、v2 必須
  - `cryptography` ライブラリは C 拡張を含むため、3.14 向けビルド済み wheel の可用性を確認する必要あり
- **Implications**:
  - 現在の依存関係（Pydantic v2.10.0+）は互換性あり
  - Dockerfile に `build-essential` 追加が必要になる可能性（wheel 不足時のソースビルド対応）
  - Python 3.14 公式 Docker イメージ（`python:3.14-slim`）の利用が前提

### Next.js 15 / React 19 破壊的変更調査
- **Context**: Frontend を Next.js 14 → 15、React 18 → 19 へ更新するための互換性確認
- **Sources Consulted**:
  - Next.js 15 Upgrade Guide: [Next.js 15 Upgrade Guide](https://nextjs.org/docs/app/guides/upgrading/version-15)
  - Next.js 15 Blog: [Next.js Blog](https://nextjs.org/blog/next-15)
  - Dynamic APIs are Asynchronous: [Next.js Dynamic APIs](https://nextjs.org/docs/messages/sync-dynamic-apis)
  - GitHub Issue #70899: [GitHub Issue #70899](https://github.com/vercel/next.js/issues/70899)
- **Findings**:
  - **Critical Breaking Change**: `params`, `searchParams`, `cookies()`, `headers()`, `draftMode()` が非同期 API に変更
  - 既存コードで同期的に `params.containerId` のようにアクセスしている箇所は修正が必要
  - Next.js 公式 codemod が提供されている: `npx @next/codemod@canary upgrade latest`
  - React 19 では `useFormState` → `useActionState` に名称変更
  - `@types/react` と `@types/react-dom` を React 19 対応版に更新が必要
- **Implications**:
  - `frontend/app/inspector/[containerId]/page.tsx`: `useParams()` と `useSearchParams()` 使用箇所の確認が必要
  - `frontend/app/oauth/callback/page.tsx`: `useSearchParams()` 使用箇所の確認が必要
  - ただし、これらは Client Component（`'use client'`）のため、Next.js 15 でも hooks は同期的に動作する（Server Component の `params` prop のみ非同期化）
  - `eslint-config-next` を 15 系に更新必要

### DevContainer 構成調査
- **Context**: Backend/Frontend 両方の開発をサポートする DevContainer 環境の設計
- **Sources Consulted**:
  - VS Code DevContainer Docs: [VS Code DevContainer Docs](https://code.visualstudio.com/docs/devcontainers/create-dev-container)
  - Connect to multiple containers: [Connect to multiple containers](https://code.visualstudio.com/remote/advancedcontainers/connect-multiple-containers)
  - Stack Overflow: docker-compose DevContainer patterns
- **Findings**:
  - docker-compose ベースの DevContainer は `dockerComposeFile` プロパティで定義
  - 複数サービス（backend, frontend）を持つ場合、`service` プロパティで接続先を指定
  - VS Code 拡張機能は `customizations.vscode.extensions` で定義
  - `postCreateCommand` でコンテナ起動後の初期化処理を実行可能
  - `forwardPorts` でホストへのポートフォワーディングを設定
- **Implications**:
  - Backend サービスをメイン DevContainer として構成（Docker ソケットアクセスが必要なため）
  - Frontend は別ターミナルまたは別 VS Code ウィンドウで接続可能
  - 単一の `.devcontainer/devcontainer.json` で docker-compose 参照が推奨

### Node.js 22 調査
- **Context**: Node.js 18 → 22 への更新影響確認
- **Sources Consulted**:
  - Node.js Release Schedule: [Node.js Release Schedule](https://nodejs.org/en/about/releases/)
- **Findings**:
  - Node.js 22 は 2024年10月より Maintenance LTS（セキュリティ修正のみ）
  - Node.js 24 が次期 Active LTS 候補（2025年10月予定）
  - `node:22-alpine` イメージは Docker Hub で利用可能
  - ESM サポート、`fetch` API 標準化など Node.js 18 からの主要な変更点あり
- **Implications**:
  - 将来的な Node.js 24 移行計画を文書化する必要あり
  - 現時点では 22 で問題なし

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| docker-compose DevContainer | 既存 docker-compose.yml を拡張し DevContainer として利用 | 既存構成の再利用、設定の一元化 | compose ファイルの複雑化 | 推奨アプローチ |
| 単一イメージ DevContainer | Python + Node.js を含む単一イメージを構築 | シンプルな構成 | イメージサイズ増大、ビルド時間増加 | 非推奨 |
| 複数 DevContainer | backend/.devcontainer と frontend/.devcontainer を分離 | 明確な分離 | コンテキスト切り替えが煩雑 | 代替案として検討可能 |

## Design Decisions

### Decision: workspace サービス型 DevContainer の採用
- **Context**: Backend と Frontend の両方を開発可能な統合環境が必要（レビュー指摘: Critical Issue 1 対応）
- **Alternatives Considered**:
  1. Backend サービスに接続する DevContainer — Node.js が含まれないため Frontend 開発不可
  2. 複数 DevContainer — backend/.devcontainer と frontend/.devcontainer を分離（切替が煩雑）
  3. workspace サービス追加 — Python 3.14 + Node.js 22 同梱の開発専用コンテナ
- **Selected Approach**: **workspace サービス**を追加し、VS Code が接続。リポジトリルートをマウントし、Backend/Frontend 両方の開発を単一ウィンドウで可能にする
- **Rationale**: 
  - 既存の開発環境構成を最大限再利用できる
  - Python と Node.js 両方が workspace 内で利用可能
  - `docker compose exec` で backend/frontend サービスに対してテスト実行可能
  - Docker ソケットマウントにより、workspace から Docker 操作も可能
- **Trade-offs**:
  - (+) 単一 VS Code ウィンドウで全開発が完結
  - (+) リポジトリルート全体にアクセス可能
  - (-) workspace イメージのビルドが必要（Python + Node.js 同梱）
  - (-) DevContainer 専用の compose オーバーライドファイルが必要
- **Follow-up**: `.devcontainer/Dockerfile.workspace` と `docker-compose.devcontainer.yml` を作成

### Decision: Client Component の params/searchParams は修正不要
- **Context**: Next.js 15 の破壊的変更への対応方針
- **Alternatives Considered**:
  1. 全ファイルを await/async 対応に修正
  2. Client Component は現状維持、Server Component のみ対応
- **Selected Approach**: Client Component（`'use client'`）内での `useParams()`, `useSearchParams()` は同期的に動作するため修正不要
- **Rationale**: 
  - Next.js 15 の非同期化は Server Component の `params` prop に適用される
  - 既存の Client Component で使用している hooks（`useParams`, `useSearchParams`）は React hooks であり、同期的に値を返す
- **Trade-offs**:
  - (+) 既存コードの変更を最小化できる
  - (-) 将来 Server Component 化する場合は修正が必要
- **Follow-up**: 公式 codemod を実行し、修正が必要な箇所がないか確認

### Decision: Python 3.14 ビルド環境の強化
- **Context**: C 拡張を含む依存関係（cryptography 等）のビルド対応
- **Alternatives Considered**:
  1. ビルド依存関係を追加せず wheel のみに依存
  2. build-essential 等をプリインストール
- **Selected Approach**: Dockerfile に `build-essential`, `libffi-dev`, `libssl-dev` を追加し、ソースビルドにも対応
- **Rationale**: 
  - Python 3.14 向けの prebuilt wheel が全ての依存関係で利用可能とは限らない
  - CI/CD での再現可能なビルドを保証する
- **Trade-offs**:
  - (+) 任意の依存関係をインストール可能
  - (-) イメージサイズが若干増加
- **Follow-up**: マルチステージビルドでビルド依存関係を最終イメージから除外

### Decision: パッチレベルまでのバージョン固定（レビュー指摘: Critical Issue 2 対応）
- **Context**: 要件にて「Python/Node/Next/React はパッチ番号まで固定」が明記されている
- **Alternatives Considered**:
  1. `>=` や `^` によるセマンティックバージョン範囲指定
  2. パッチレベルまで完全固定（`==` / 固定バージョン）
- **Selected Approach**: すべての依存関係を**パッチレベルまで固定**し、ロックファイルをコミット
- **Rationale**: 
  - 再現可能なビルドを保証
  - CVE 修正版の追跡が容易
  - 環境間での差異を排除
- **Trade-offs**:
  - (+) 完全な再現性
  - (+) セキュリティパッチの明示的な適用
  - (-) 依存関係更新時の手動作業が増加
- **Implementation**:
  - Docker イメージ: `python:3.14.2-slim`, `node:22.21.1-alpine`
  - Python: `requirements.txt` で `==` 指定
  - Node.js: `package.json` から `^` を除去、`package-lock.json` 必須コミット

### Decision: docker compose exec によるテスト実行（レビュー指摘: Critical Issue 3 対応）
- **Context**: テストスクリプトが固定コンテナ名に依存しており、環境によって壊れる可能性がある
- **Alternatives Considered**:
  1. `docker exec <container-name>` — プロジェクト名でコンテナ名が変わる
  2. `docker compose exec <service-name>` — サービス名ベースで環境非依存
- **Selected Approach**: **`docker compose exec`** を使用し、サービス名（backend, frontend）で実行
- **Rationale**: 
  - プロジェクト名やコンテナ命名規則に依存しない
  - CI/CD 環境でも再現可能
  - `-T` フラグで TTY なし実行をサポート
- **Trade-offs**:
  - (+) 環境非依存で再現可能
  - (+) compose ファイルの切り替えも可能（`COMPOSE_FILE` 環境変数）
  - (-) Docker Compose が起動していることが前提

## Risks & Mitigations
- **Python 3.14 wheel 未提供リスク** — Dockerfile にビルドツールを追加し、ソースビルド可能にする
- **Next.js 15 破壊的変更の見落とし** — 公式 codemod を実行し、型エラーを CI で検出
- **テスト環境の差異** — DevContainer 内でのみテストを実行するポリシーを強制（`docker compose exec` 使用）
- **Node.js 22 EOL リスク** — Node.js 24 への移行計画を文書化
- **バージョン固定による更新コスト** — 定期的なセキュリティレビューと依存関係更新プロセスを確立

## References
- [FastAPI Release Notes](https://fastapi.tiangolo.com/release-notes/) — Python 3.14 サポート情報
- [Pydantic GitHub Issue #11613](https://github.com/pydantic/pydantic/issues/11613) — Python 3.14 対応状況
- [Next.js 15 Upgrade Guide](https://nextjs.org/docs/app/guides/upgrading/version-15) — 破壊的変更と移行手順
- [VS Code DevContainer Docs](https://code.visualstudio.com/docs/devcontainers/create-dev-container) — DevContainer 構成ガイド
- [Connect to multiple containers](https://code.visualstudio.com/remote/advancedcontainers/connect-multiple-containers) — マルチサービス DevContainer
