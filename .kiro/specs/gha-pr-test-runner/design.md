# Design Document

## Overview
本機能は、PR 作成・更新時に既存テスト（バックエンド Pytest、フロントエンド Jest、E2E/Playwright）を GitHub Actions 上で確実に実行し、ubuntu-slim ランナー互換と nektos/act によるローカル再現性を提供する。レビュアーはクラウド実行結果で安全にマージ可否を判断でき、開発者は push 前に act で失敗を検知できる。

### Goals
- PR イベントでバックエンド・フロントエンド・E2E を自動実行し、失敗時にマージをブロックする。
- すべてのジョブを ubuntu-slim ランナー上で安定動作させる。
- act `pull_request` でクラウドと同一構成をローカル再現できるようにする。

### Non-Goals
- 新規テストケースの追加やテストロジック変更。
- CI 以外のデプロイ／リリースフローの改変。
- パフォーマンス最適化（キャッシュ設計は最小限）。

## Architecture

### Existing Architecture Analysis
- 現行 CI: `.github/workflows/e2e-tests.yml` が push/PR で `ubuntu-latest` ランナー上にて E2E のみ実行。Node/Python セットアップ、Playwright 依存インストール、`docker-compose.test.yml` で frontend/backend を起動し `npm run test:e2e` を実行。
- テスト配置: フロントは Jest/Playwright、バックは Pytest。Docker Compose ベースの統合実行が前提。

### High-Level Architecture
```mermaid
graph TB
  A[PR open/reopen/synchronize] --> B[GitHub Actions workflow (ubuntu-slim)]
  B --> C[backend-unit job (Pytest)]
  B --> D[frontend-unit job (Jest)]
  B --> E[e2e job (Playwright + docker-compose.test.yml)]
  E --> F[docker compose up frontend+backend]
  C --> G[status check]
  D --> G
  E --> G
  G --> H[PR required checks / review]
  I[Developer local `act pull_request`] --> J[Same jobs on ubuntu-slim image]
  J --> K[Local status parity]
```

### Technology Alignment
- ランナー: GitHub Actions ubuntu-slim (1 vCPU, 2GB RAM 想定) を採用し、既存 `ubuntu-latest` から移行。
- 言語/ツール: Node 18, Python 3.11, Playwright, docker-compose（既存踏襲）。
- 新規要素: act 用の既定イメージ/シークレット設定（`.actrc` + サンプル env/secrets ファイル）。

### Key Design Decisions
- **Decision**: ランナーを `ubuntu-24.04-slim` 相当へ統一。
  - Context: 1 vCPU slim ランナー指定要件。
  - Alternatives: `ubuntu-latest` 継続 / `ubuntu-22.04` slim。
  - Selected Approach: 24.04 slim。
  - Rationale: 最新 LTS ベースで slim プレビュー要件を満たす。
  - Trade-offs: パッケージ不足時に追加 `apt-get` が必要、リソース上限によりタイムアウトしやすい。
- **Decision**: ワークフローを「ユニット（バック/フロント）＋E2E」の 1 ファイル内 3 ジョブに分割し、依存を明示。
  - Context: 既存 E2E のみで網羅不足。
  - Alternatives: 複数ファイルに分割 / 単一ジョブ統合。
  - Selected Approach: 単一ファイル内の 3 ジョブ（needs で依存制御不要、並列実行可）。
  - Trade-offs: ファイルは肥大化するが閲覧箇所が一箇所で済む。
- **Decision**: act 再現用に `.actrc` で pull_request イメージを slim に固定し、ローカル用 env/secrets サンプルを提供。
  - Context: ローカルとクラウドの差分最小化。
  - Alternatives: ドキュメントのみで手動指定 / Make ターゲットで包む。
  - Selected Approach: `.actrc` で既定化＋サンプルファイル。
  - Trade-offs: ファイルが増えるが開発者の手順が単純化。

## System Flows
### CI フロー（PR）
```mermaid
sequenceDiagram
  participant Dev as Developer
  participant GH as GitHub
  participant WF as GHA Workflow (slim)
  participant BE as backend-unit
  participant FE as frontend-unit
  participant EE as e2e
  Dev->>GH: Open/Update PR
  GH->>WF: trigger pull_request
  WF->>BE: run pytest
  WF->>FE: run jest
  WF->>EE: run docker-compose + playwright
  BE-->>WF: status (pass/fail)
  FE-->>WF: status (pass/fail)
  EE-->>WF: status (pass/fail)
  WF-->>GH: combined status check
```

### ローカル再現フロー（act）
```mermaid
flowchart LR
  A[Developer] --> B[act pull_request -j <job>]
  B --> C[ubuntu-24.04-slim image]
  C --> D[Jobs: backend-unit / frontend-unit / e2e]
  D --> E[Local results & logs]
```

## Components and Interfaces

### Workflow: `.github/workflows/ci-tests.yml`（新規）
- Responsibility: PR/push で 3 ジョブを起動し、キャッシュとアーティファクト収集を行う。
- Dependencies: `actions/checkout@v4`, `actions/setup-node@v4`, `actions/setup-python@v4`, `docker-compose`, `actions/upload-artifact@v4`.
- Interfaces:
  - Triggers: `pull_request` (main/develop 等)、`push` (main/develop)。
  - Env: `CI=true`, `PLAYWRIGHT_BASE_URL`, `PYTHONPATH` など既存に準拠。
  - Artifacts: Playwright レポート、テスト結果（必要に応じ）。

### Job: backend-unit
- Responsibility: backend/ 配下の Pytest を実行。
- Inputs: Python 3.11、pip キャッシュ、`backend/requirements.txt`。
- Behavior: `pip install -r requirements.txt` → `pytest`。
- Outputs: テスト結果（将来的に `pytest --junitxml` でアーティファクト化可）。

### Job: frontend-unit
- Responsibility: frontend の Jest/Testing Library を実行。
- Inputs: Node 18、npm キャッシュ、`frontend/package-lock.json`。
- Behavior: `npm ci` → `npm test -- --runInBand --ci`。
- Outputs: Jest レポート（必要ならアーティファクト化）。

### Job: e2e-playwright
- Responsibility: docker-compose.test.yml でサービスを起動し、Playwright E2E を実行。
- Inputs: Node 18、Python 3.11、docker-compose、Playwright 依存（`npx playwright install --with-deps`）。必要なら slim 向け追加パッケージ（例: `libnss3`, `libatk1.0-0` 等）を apt で補完。
- Behavior: compose 起動→ヘルス待機→`npm run test:e2e`。失敗時ログとアーティファクト収集。
- Outputs: Playwright レポート、テスト結果、compose ログ。

### Local reproducibility: act
- Files: `.actrc`（pull_request の既定イメージを slim に固定）、`act.secrets.example` / `act.env.example`（必要シークレット・環境変数のプレースホルダー）。
- Usage: `act pull_request -j backend-unit|frontend-unit|e2e`。クラウド依存部（例: GitHub Token 必須箇所）はダミー値またはスキップ条件をドキュメント化。

## Error Handling
- ジョブ失敗時: `fail-fast` オフ（並列ジョブ結果をすべて取得）、ステップごとに `if: always()` でログ・アーティファクトを保存。
- タイムアウト: slim 1 vCPU 向けに各ジョブに適切な `timeout-minutes` を設定（E2E は現行 30 分以内に維持）。
- リトライ: テスト自体はリトライしない。パッケージ取得失敗時は `max-attempts` 付きステップで再試行を検討。

## Testing Strategy
- Unit: backend Pytest、frontend Jest を CI で毎回実行。act でも同一コマンドを提供。
- Integration/E2E: Playwright E2E を slim 上で実行し、サービス起動待ちをスクリプト化。
- Smoke (local): act で主要ジョブを個別に実行し、キャッシュ有無での動作を確認。

## Security Considerations
- Secrets: act 用のサンプルファイルを提供し、実値は開発者ローカルでのみ設定。リポジトリには含めない。
- Token/Licenses: GitHub Token 等が不要な場合は無効化、必要な場合はダミー許容かスキップ条件を明記。
- ログ: アーティファクトに秘匿情報を含めないよう、テスト出力でトークンやパスワードを出さないことをガイド。

## Performance & Scalability
- slim 1 vCPU での実行時間を考慮し、`--runInBand`（Jest）や適切な Playwright 並列度を設定。
- npm/pip キャッシュを有効化し、再実行時間を短縮。

## Migration Strategy
```mermaid
flowchart TD
  A[Phase 1: 3ジョブ構成の新WF追加\nubuntu-slim対応・act設定追加] --> B[Phase 2: E2E旧WFをslim化/統合\n必須チェックを新WFに付け替え]
  B --> C[Phase 3: 旧設定の整理\n不要ファイル削除とドキュメント更新]
```
- Phase 1: 新ワークフロー追加・act 設定投入（既存 e2e-tests.yml は一時並存可）。
- Phase 2: slim での安定動作を確認後、必須チェックを新ワークフローに切替。
- Phase 3: 旧ワークフローや不要ステップを削除し、README/開発手順を更新。
