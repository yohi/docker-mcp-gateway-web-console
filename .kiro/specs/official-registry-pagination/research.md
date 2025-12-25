# Research Log: official-registry-pagination

## Summary

Official MCP Registry API のカーソルベースページネーション実装に向けた調査を実施。API レスポンス構造の確認、既存実装の分析、ページネーション戦略の評価を行った。

**Key Findings**:
1. Official Registry API は `metadata.nextCursor` と `metadata.count` を含むレスポンスを返却
2. 現在の実装は単一リクエストのみで、`nextCursor` を無視している
3. カーソルベースページネーションは既存のキャッシュ機構と統合可能

## Research Log

### Topic: Official Registry API Response Structure

**Investigation**: Official Registry API のレスポンス形式を確認

**Sources**:
- Official Registry API: `https://registry.modelcontextprotocol.io/v0/servers`

**Findings**:
```json
{
  "servers": [
    {
      "server": {
        "name": "ai.mcpcap/mcpcap",
        "version": "0.6.0",
        ...
      },
      "_meta": {...}
    },
    ...
  ],
  "metadata": {
    "nextCursor": "ai.mcpcap/mcpcap:0.6.0",
    "count": 30
  }
}
```

- `servers`: サーバーエントリの配列（最大30件）
- `metadata.nextCursor`: 次ページ取得用のカーソル文字列（最終ページでは省略または null）
- `metadata.count`: 現在のレスポンスに含まれるサーバー数

**Implications**:
- カーソルが存在する限り、追加ページが利用可能
- カーソルは `?cursor={nextCursor}` パラメータで次ページリクエストに使用
- 最終ページではカーソルが存在しない

### Topic: Existing Implementation Analysis

**Investigation**: 現在の `CatalogService._fetch_from_url` の実装を分析

**Sources**:
- `backend/app/services/catalog.py`

**Findings**:
- 単一リクエストのみ発行
- `metadata.nextCursor` を無視
- レスポンスをパースして `CatalogItem` に変換
- キャッシュ機構は `source_url` をキーとして使用

**Implications**:
- ページネーション取得は新規メソッドとして実装可能
- 既存のキャッシュ機構と統合可能（全ページ取得完了後にキャッシュ）
- スキーマ変換ロジック（`_convert_explore_server`）は再利用可能

### Topic: Pagination Strategy Evaluation

**Investigation**: ページネーション実装の戦略を評価

**Options Considered**:

1. **Option A: Backend Batch Fetch (選択)**
   - バックエンドで全ページを一括取得
   - フロントエンドは既存の無限スクロール UI をそのまま利用
   - キャッシュ機構と統合可能
   - **Pros**: フロントエンド変更不要、キャッシュ効率が高い
   - **Cons**: 初回ローディング時間が長くなる可能性

2. **Option B: Frontend Progressive Fetch**
   - フロントエンドで段階的にページ取得
   - バックエンドは単一ページのみ返却
   - **Pros**: 初回表示が高速
   - **Cons**: フロントエンド実装が複雑、キャッシュ効率が低い

**Decision**: Option A を選択

**Rationale**:
- フロントエンド変更が不要で、既存の無限スクロール UI を維持
- バックエンドでキャッシュすることで、2回目以降のアクセスが高速
- Official Registry の全エントリ数は数百件程度と想定され、一括取得でも問題なし

### Topic: Rate Limiting and Load Considerations

**Investigation**: 上流サービスへの負荷とレート制限を考慮

**Findings**:
- Official Registry のレート制限ポリシーは公開されていない
- 既存実装では単一リクエストのみのため、レート制限の影響は未確認
- ページ間遅延を挿入することで、上流サービスへの負荷を軽減可能

**Decision**: ページ間遅延を実装

**Configuration**:
- デフォルト遅延: 100ms
- 環境変数 `CATALOG_OFFICIAL_PAGE_DELAY` で調整可能

**Rationale**:
- 上流サービスへの負荷を軽減
- レート制限リスクを低減
- 100ms は体感的に問題ないレベル

### Topic: Timeout and Limit Configuration

**Investigation**: 無限ループ防止とタイムアウト設定を検討

**Findings**:
- Official Registry の全エントリ数は不明（数百件と想定）
- 無限ループを防止するため、最大ページ数とタイムアウトの設定が必要

**Decision**: 以下の制限を設定

| Setting | Default | Rationale |
|---------|---------|-----------|
| `CATALOG_OFFICIAL_MAX_PAGES` | 20 | 最大600件（20ページ × 30件）を取得 |
| `CATALOG_OFFICIAL_FETCH_TIMEOUT` | 60 | 全ページ取得の合計タイムアウト秒数 |

**Implications**:
- 上限到達時は取得済みデータを返却し、警告メッセージで通知
- タイムアウト時も取得済みデータを返却
- 環境変数で調整可能

### Topic: Error Handling Strategy

**Investigation**: エラーハンドリング戦略を評価

**Scenarios**:
1. 初回ページ取得失敗 → `CatalogError` をスロー
2. 途中ページ取得失敗 → 取得済みデータを返却（部分成功）
3. レート制限（429） → `CatalogError` をスロー
4. タイムアウト → 取得済みデータを返却（部分成功）
5. 最大ページ数到達 → 取得済みデータを返却（部分成功）

**Decision**: 部分成功を許容

**Rationale**:
- 初回ページ失敗時は既存のエラーハンドリングを適用
- 途中ページ失敗時は、取得済みデータをユーザーに提供することで UX を向上
- 警告メッセージでユーザーに通知

### Topic: Cache Integration

**Investigation**: 既存のキャッシュ機構との統合を検討

**Findings**:
- 現在のキャッシュは `source_url` をキーとして使用
- TTL は `catalog_cache_ttl_seconds`（デフォルト: 3600秒）
- 全ページ取得完了後の結合データをキャッシュ可能

**Decision**: 既存のキャッシュ機構をそのまま利用

**Implications**:
- キャッシュヒット時はページネーション取得をスキップ
- 2回目以降のアクセスは高速
- キャッシュ無効化時（`force_refresh=True`）は全ページ再取得

### Topic: Duplicate Handling

**Investigation**: ページ間での重複エントリの可能性を検討

**Findings**:
- Official Registry のカーソルベースページネーションは、スナップショット時点のデータを返却
- 理論的には重複の可能性は低いが、念のため重複除外を実装

**Decision**: ID ベースで重複除外を実装

**Implementation**:
```python
seen_ids: set[str] = set()
unique_items: List[CatalogItem] = []
for item in items:
    if item.id not in seen_ids:
        seen_ids.add(item.id)
        unique_items.append(item)
```

**Rationale**:
- 安全性を優先
- パフォーマンスへの影響は軽微（数百件程度）

## Architecture Pattern Evaluation

### Pattern: Extend Existing Service (選択)

**Description**: 既存の `CatalogService` に新規メソッド `_fetch_official_registry_with_pagination` を追加

**Pros**:
- 既存のキャッシュ機構、エラーハンドリング、スキーマ変換を再利用
- フロントエンド変更不要
- テスト容易性が高い

**Cons**:
- `CatalogService` のコード量が増加

**Decision**: このパターンを選択

**Rationale**:
- 既存の実装と一貫性を保つ
- コード重複を避ける
- テストとメンテナンスが容易

### Alternative: Create Separate Pagination Service

**Description**: ページネーション専用のサービスクラスを作成

**Pros**:
- 関心の分離
- `CatalogService` のコード量を抑制

**Cons**:
- キャッシュ機構、エラーハンドリング、スキーマ変換の重複
- 複雑性が増加

**Decision**: 採用しない

**Rationale**:
- ページネーション取得は `CatalogService` の責務の範囲内
- 既存の実装と統合することで、コード重複を避ける

## Design Decisions

### Decision 1: Cursor-Based Pagination

**Context**: Official Registry API はカーソルベースページネーションを採用

**Options**:
- A: カーソルベースページネーション（選択）
- B: オフセットベースページネーション

**Decision**: Option A

**Rationale**:
- Official Registry API の仕様に準拠
- カーソルベースはデータ変更時の一貫性が高い

### Decision 2: Backend Batch Fetch

**Context**: ページネーション取得の実装場所

**Options**:
- A: バックエンドで一括取得（選択）
- B: フロントエンドで段階的取得

**Decision**: Option A

**Rationale**:
- フロントエンド変更不要
- キャッシュ効率が高い
- 既存の無限スクロール UI を維持

### Decision 3: Partial Success Handling

**Context**: 途中ページ取得失敗時の挙動

**Options**:
- A: 取得済みデータを返却（選択）
- B: エラーをスローして全体失敗

**Decision**: Option A

**Rationale**:
- ユーザーに部分的なデータを提供することで UX を向上
- 警告メッセージで状況を通知

### Decision 4: Duplicate Removal

**Context**: ページ間での重複エントリの可能性

**Options**:
- A: ID ベースで重複除外（選択）
- B: 重複を許容

**Decision**: Option A

**Rationale**:
- 安全性を優先
- パフォーマンスへの影響は軽微

## Risks and Mitigations

### Risk 1: Official Registry Schema Changes

**Risk**: Official Registry のスキーマ変更時にパース失敗

**Likelihood**: Low
**Impact**: High

**Mitigation**:
- エラーログで早期検知
- 既存の `_convert_explore_server` でスキーマ検証
- 部分成功ハンドリングで影響を最小化

### Risk 2: Rate Limiting

**Risk**: 大量リクエストによるレート制限

**Likelihood**: Medium
**Impact**: Medium

**Mitigation**:
- ページ間遅延を挿入（デフォルト: 100ms）
- レート制限エラー時は既存のエラーハンドリングを適用
- 環境変数で遅延時間を調整可能

### Risk 3: Memory Usage

**Risk**: 大量ページ取得時のメモリ使用量増加

**Likelihood**: Low
**Impact**: Low

**Mitigation**:
- 最大ページ数制限（デフォルト: 20ページ = 600件）
- Official Registry の全エントリ数は数百件程度と想定

### Risk 4: Timeout

**Risk**: 全ページ取得に時間がかかりすぎる

**Likelihood**: Low
**Impact**: Medium

**Mitigation**:
- タイムアウト設定（デフォルト: 60秒）
- タイムアウト時は取得済みデータを返却
- 環境変数でタイムアウト時間を調整可能

## Open Questions

なし（すべての設計判断が完了）

## References

- Official MCP Registry API: https://registry.modelcontextprotocol.io/v0/servers
- Existing Implementation: `backend/app/services/catalog.py`
- Requirements: `.kiro/specs/official-registry-pagination/requirements.md`
