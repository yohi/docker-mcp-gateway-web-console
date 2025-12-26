# 実装計画

## タスク概要

本計画は、Official MCP Registry のカーソルベースページネーション対応を実装するための段階的なタスクリストです。各タスクは自然言語で「何を実現するか」を記述し、実装の詳細は `design.md` および `requirements.md` を参照します。

---

## フェーズ 1: バックエンド設定の追加 (P)

- [x] 1. ページネーション関連の設定を追加する (P)
  - Settings クラスに `catalog_official_max_pages`（デフォルト: 20）を追加する
  - Settings クラスに `catalog_official_fetch_timeout`（デフォルト: 60）を追加する
  - Settings クラスに `catalog_official_page_delay`（デフォルト: 100）を追加する
  - 環境変数による上書きをサポートする
  - Pydantic Field でデフォルト値と説明を定義する
  - _Requirements: 2.1, 2.2, 2.4, 6.1, 6.2, 6.3_

---

## フェーズ 2: カーソルページネーション取得の実装

- [x] 2. `_fetch_official_registry_with_pagination` メソッドを実装する
  - 初回リクエストをカーソルなしで発行する
  - レスポンスから `metadata.nextCursor` と `servers` を抽出する
  - カーソルが存在する場合、`?cursor={nextCursor}` パラメータ付きで次ページを取得する
  - カーソルが存在しなくなるまでループを継続する
  - 各ページの `servers` 配列を結合する
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 3. ページ間遅延を実装する
  - 各ページ取得後に `asyncio.sleep(page_delay_ms / 1000.0)` で遅延を挿入する
  - 最終ページ（カーソルなし）の場合は遅延をスキップする
  - 設定値（`catalog_official_page_delay`）を使用する
  - _Requirements: 1.4_

- [x] 4. 重複除外ロジックを実装する
  - ID ベースの重複除外を実装する（`used_ids` セットを使用）
  - `_convert_explore_server` 内で ID の一意性を保証する
  - 全ページに対して単一の `used_ids` を共有する
  - _Requirements: 1.3_

- [x] 5. 最大ページ数制限を実装する
  - ページカウンターを初期化し、各ページ取得後にインクリメントする
  - `catalog_official_max_pages` に到達したらループを停止する
  - 上限到達時は `_append_warning` で警告メッセージを設定する
  - 取得済みデータを返却する
  - _Requirements: 2.1, 2.3_

- [x] 6. 全体タイムアウトを実装する
  - ループ開始時に `start_time = time.time()` でタイムスタンプを記録する
  - 各ページ取得前に経過時間をチェックする
  - `catalog_official_fetch_timeout` を超過したらループを停止する
  - タイムアウト時は `_append_warning` で警告メッセージを設定する
  - 取得済みデータを返却する
  - _Requirements: 2.2, 2.3_

- [x] 7. エラーハンドリングを実装する
  - 初回ページ取得失敗時は `CatalogError` をスローする
  - 途中ページ取得失敗時は取得済みデータを返却する
  - 部分成功時は `_append_warning` で警告メッセージを設定する
  - 429 レスポンス時は `CatalogError(RATE_LIMITED)` をスローする
  - レート制限時に取得済みデータがある場合は部分成功として返却する
  - _Requirements: 3.1, 3.2, 3.3_

---

## フェーズ 3: 既存コードとの統合

- [x] 8. `_fetch_from_url` メソッドを拡張する
  - Official Registry URL 判定ロジックを追加する（`source_url == settings.catalog_official_url`）
  - Official Registry の場合は `_fetch_official_registry_with_pagination` を呼び出す
  - それ以外は既存の単一リクエスト処理を維持する
  - _Requirements: 1.1_

- [x] 9. ログ出力を追加する (P)
  - 各ページ取得時に `logger.info` でページ番号と取得件数を出力する
  - 全ページ取得完了時に合計ページ数と合計件数を出力する
  - 警告発生時に詳細をログに記録する
  - _Requirements: 5.2_

---

## フェーズ 4: テストの実装

- [ ] 10. ページネーション取得ロジックの単体テストを作成する (P)
  - 複数ページのモックレスポンスを準備する（3ページ、各30件）
  - カーソルが正しく処理されることを確認する
  - ページ結合が正しく行われることを確認する（合計90件）
  - 重複除外が機能することを確認する
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 11. 制限・タイムアウトの単体テストを作成する (P)
  - 最大ページ数制限が機能することを確認する（21ページ目で停止）
  - タイムアウトが機能することを確認する（60秒超過で停止）
  - 警告メッセージが設定されることを確認する
  - 取得済みデータが返却されることを確認する
  - _Requirements: 2.1, 2.2, 2.3_

- [ ] 12. エラーハンドリングの単体テストを作成する (P)
  - 初回ページ失敗時に `CatalogError` がスローされることを確認する
  - 途中ページ失敗時に部分成功データが返却されることを確認する
  - レート制限（429）時の動作を確認する
  - 部分成功時の警告メッセージを確認する
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 13. Official ソースでのエンドツーエンド統合テストを作成する (P)
  - モックサーバーを使用した複数ページ取得のテストを実装する
  - 30件を超えるサーバーが返却されることを確認する
  - キャッシュ統合が正しく機能することを確認する
  - _Requirements: 1.3, 4.1, 4.2, 4.3, 5.3_

- [ ] 14. キャッシュ動作の統合テストを作成する (P)
  - 初回リクエストでページネーション取得が実行されることを確認する
  - 2回目のリクエストでキャッシュが使用されることを確認する
  - キャッシュ有効期限後に再取得が行われることを確認する
  - _Requirements: 4.1, 4.2, 4.3_

---

## フェーズ 5: ドキュメント更新 (P)

- [ ] 15. 環境変数のドキュメントを更新する (P)
  - `CATALOG_OFFICIAL_MAX_PAGES` の説明を追加する（デフォルト: 20、最大600件）
  - `CATALOG_OFFICIAL_FETCH_TIMEOUT` の説明を追加する（デフォルト: 60秒）
  - `CATALOG_OFFICIAL_PAGE_DELAY` の説明を追加する（デフォルト: 100ms）
  - 推奨値と使用例を記載する
  - _Requirements: 6.1, 6.2, 6.3_

- [ ] 16. 動作仕様のドキュメントを更新する (P)
  - Official Registry のページネーション動作を説明する
  - カーソルベース取得の仕組みを説明する
  - 部分成功時の挙動を説明する
  - 制限とタイムアウトの動作を説明する
  - _Requirements: 1.1, 2.1, 2.2, 3.1_

---

## 完了基準

すべてのタスクが完了し、以下が満たされた時点で本機能は完成とする：

1. [ ] Official ソース選択時に30件を超えるサーバーが表示される
2. [ ] `cd backend && pytest tests/unit/catalog/test_official_pagination.py -v` が成功する
3. [ ] `cd backend && pytest tests/integration/catalog/test_source_official.py -v` が成功する
4. [ ] 部分成功時に警告メッセージが表示される
5. [ ] 既存のテストスイートが引き続きパスする（`cd backend && pytest -v`）
6. [ ] ドキュメントが更新されている
