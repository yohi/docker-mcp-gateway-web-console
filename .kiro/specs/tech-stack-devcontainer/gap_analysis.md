# ギャップ分析: 技術スタック更新とDevContainer

## 1. 現状調査

### ドメイン資産とアーキテクチャ
- **Backend**: FastAPI (Python 3.11), Pydantic V2, Docker化済み。
- **Frontend**: Next.js 14 (App Router), React 18, TypeScript, Docker化済み。
- **Infrastructure**: ローカル実行用の `docker-compose.yml` が存在する。
- **Missing**: `.devcontainer` 設定が完全に欠落している。

### 規約
- **Backend**: 標準的な FastAPI 構成 (`app/main.py`, `app/api`, `app/models`)。`requirements.txt` を使用。
- **Frontend**: Next.js App Router 構成 (`app/`)。`npm` と `package.json` を使用。
- **Testing**: `pytest` (Backend), `jest`/`playwright` (Frontend)。現在はローカルまたは単純な Docker 実行を想定。

### 統合部分
- **Backend -> Frontend**: REST API。
- **Auth**: 外部プロバイダとの OAuth フロー。
- **Docker Socket**: Backend は Docker ソケットをマウントしている。

## 2. 要件実現可能性分析

### Requirement 1: DevContainer 環境
- **ギャップ**: 機能が存在しない。
- **実現可能性**: 高。標準的な VS Code DevContainer 仕様を適用可能。
- **制約**: Python と Node.js の両方をサポートする必要がある。マルチコンテナまたはモノリシックイメージのアプローチが必要だが、サービスが分かれているため docker-compose ベースの DevContainer が最適。

### Requirement 2: テスト実行ポリシー (コンテナ化)
- **ギャップ**: 既存のスクリプト (`scripts/run-e2e-tests.sh` 等) がローカルコマンドを呼び出している可能性がある。
- **実現可能性**: 高。スクリプトを更新し、`docker exec` または `devcontainer exec` でコマンドをラップする。

### Requirement 3: Backend Python 3.14
- **ギャップ**: 現在は 3.11。
- **実現可能性**: 中/高。Python 3.14 (2025年10月リリース想定) は主要ライブラリでサポートされるはずである。
- **リスク**: `cryptography`, `pydantic-core`, `numpy` (使用している場合) のバイナリ wheel が特定のアーキテクチャで 3.14 向けに提供されていない可能性があり、ソースビルド (ビルド時間の増加、Cコンパイラが必要) が発生する可能性がある。

### Requirement 4: Frontend Node 22 / Next 15 / React 19
- **ギャップ**: 現在は Node 18 / Next 14 / React 18。
- **実現可能性**: 中。
- **破壊的変更**:
  - **Next.js 15**: Server Components における `params` と `searchParams` が Promise に変更された。これらを同期的に使用している既存コードは破損する。
  - **React 19**: API の変更 (例: `useFormState` -> `useActionState`)、非推奨機能の削除。
  - **依存関係**: `jest` と `playwright` の React 19 との互換性を検証する必要がある。

### Requirement 5 & 6: 回帰防止と互換性
- **ギャップ**: ビルド失敗 (ネイティブ拡張) 時に CI ログが十分に詳細であることを確認する必要がある。

## 3. 実装アプローチの選択肢

### Option A: 標準アップグレードと DevContainer 追加 (推奨)
- **戦略**:
  - `Dockerfile` をインプレースで更新する。
  - 破壊的なコード変更 (Next.js 15 の非同期 params) を修正する。
  - `.devcontainer` フォルダと `docker-compose.yml` を追加する。
  - `scripts/` を更新してコンテナ実行を使用するようにする。
- **トレードオフ**:
  - ✅ 要件に直接対応できる。
  - ✅ 構造的な変更を最小限に抑えられる。
  - ❌ 「ビッグバン」アップグレードにより、複数の箇所が同時に壊れた場合のデバッグが難しくなる可能性がある。

### Option B: 段階的アップグレード
- **戦略**:
  - フェーズ 1: *現在の* スタックでの DevContainer 導入。
  - フェーズ 2: Backend アップグレード。
  - フェーズ 3: Frontend アップグレード。
- **トレードオフ**:
  - ✅ 安全で、問題の切り分けが容易。
  - ❌ 時間がかかり、複数の PR/レビュー が必要。
  - ❌ 一時的に DevContainer でレガシーなスタックをサポートすることになる。

## 4. 実装の複雑性とリスク

- **工数**: **M (3-7 日)**
  - DevContainer のセットアップは単純 (1-2 日)。
  - Backend のアップグレードは依存関係のビルド失敗がなければ低工数 (1 日)。
  - Frontend のアップグレードは、Next.js 15 の破壊的変更に対するコード修正 (codemods と手動修正) を含む (2-4 日)。
- **リスク**: **Medium**
  - **理由**: Next.js 15 と React 19 はコード修正を必要とする破壊的変更を導入する。Python 3.14 のネイティブ拡張ビルド失敗は潜在的なブロッカーであり、Dockerfile の調整 (build-essential の追加等) が必要になる可能性がある。

## 5. 設計フェーズへの推奨事項

- **推奨アプローチ**: **Option A** (論理的にコミット/タスクを分割可能だが、1つのスペック範囲内で実施)。
- **主な決定事項**:
  - Backend と Frontend サービス + DB を実行するために `docker-compose` ベースの DevContainer を使用する。
  - `node:22-alpine` と `python:3.14-slim` を使用する。
  - React 19 移行のために必要であれば `legacy-peer-deps` を有効にするが、クリーンインストールを目指す。
- **要調査**:
  - Next.js 15 コンパイラ/トランスパイルに対する `playwright` と `jest` の設定調整を検証する。
  - Linux/ARM64 および AMD64 上での Python 3.14 向け `cryptography` wheel の可用性を確認する。

## Output Checklist
- [x] Requirement-to-Asset Map
- [x] Options A/B
- [x] Effort/Risk Assessment
- [x] Design Recommendations
