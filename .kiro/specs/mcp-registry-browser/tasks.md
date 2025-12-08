# Implementation Plan - MCP Registry Browser

## 1. Backend Implementation

- [x] 1.1. カタログ用データモデルの作成
  - `app/schemas/catalog.py`を作成し、`RegistryItem` Pydanticモデルを定義する
  - 外部レジストリJSONの構造（`name`, `description`, `vendor`, `image`, `required_envs`等）に合わせる
  - _Requirements: 1.1_

- [x] 1.2. CatalogServiceの実装
  - `app/services/catalog.py`を作成する
  - `fetch_catalog()`メソッドを実装し、`https://raw.githubusercontent.com/docker/mcp-registry/main/registry.json`からデータを取得する
  - シンプルなメモリ内キャッシュ（またはTTL付きLRUキャッシュ）を実装して都度の外部通信を防ぐ
  - 取得失敗時のエラーハンドリング（空リスト返却など）を実装する
  - _Requirements: 1.1, 1.2_

- [x] 1.3. Catalog API Routerの実装
  - `app/routers/catalog.py`を作成し、`GET /api/catalog`エンドポイントを実装する
  - `main.py`にルーターを登録する
  - `CatalogService`を利用してデータを返却するテストコード(`tests/api/test_catalog.py`)を作成する
  - _Requirements: 1.3_

## 2. Frontend Implementation

- [x] 2.1. API Clientの更新
  - `frontend/lib/api/catalog.ts`を作成し、`fetchCatalog`関数を実装する
  - 型定義をBackendのレスポンスに合わせる
  - _Requirements: 1.3_

- [x] 2.2. Catalog Page & Card Componentの実装
  - `frontend/app/catalog/page.tsx`を作成し、グリッドレイアウトを実装する
  - `frontend/components/catalog/CatalogCard.tsx`を作成し、サーバー情報を表示する
  - `useContainers`フックを利用して、インストール済み（同名/同イメージ実行中）の場合にステータス表示を切り替えるロジックを入れる
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 2.3. Install Modalの実装 (Bitwarden Integration)
  - `frontend/components/catalog/InstallModal.tsx`を作成する
  - `RegistryItem.required_envs`に基づき動的に入力フォームを生成する
  - 環境変数名に安易なヒューリスティック(KEY, SECRET等)がある場合、既存の`BitwardenSelector`を表示する
  - _Requirements: 3.1_

- [x] 2.4. Install Actionの統合
  - モーダルの「インストール」ボタン押下時に `POST /api/containers/install` (既存API利用想定) を呼び出す処理を実装する
  - `useInstallation`フック（既存または新規作成）でインストール中のローディング表示を行う
  - 成功/失敗のトースト通知を実装する
  - _Requirements: 3.2, 3.3_

## 3. Verification

- [ ] 3.1. E2Eテストの追加
  - カタログページを開き、リストが表示されることを確認する
  - 任意のサーバーのインストールフローがモーダル経由で完了することを確認するテストを追加する
  - _Requirements: 2.1, 3.2_
