# Gap Analysis: Gateway Console Refactoring

## 1. Analysis Summary

本分析では、現在のモノリシックな FastAPI/SQLite 構成から、Redis と Worker を導入したステートレス・非同期アーキテクチャへの移行ギャップを評価しました。

- **主要なギャップ**: `StateStore` が全データを SQLite に保存しているため、セッション等の揮発性データを Redis へ分離する必要があります。また、現在プロセス内タスクとして実行されているジョブ処理を、Redis キューを介した Worker コンテナへ切り出す必要があります。
- **セキュリティ**: ログのサニタイズ機構と厳密な SSRF 対策の実装、および暗号化キー管理の厳格化（Fail Fast）が必要です。
- **推奨アプローチ**: 「ハイブリッドアプローチ」を推奨します。既存の `StateStore` を永続化用として維持しつつ、Redis 用のリポジトリ層と Worker サービスを新規構築し、段階的に移行することでリスクを低減します。

## 2. Requirement-to-Asset Map & Gaps

| Requirement | Affected Assets | Current State | Gap / Needs | Type |
| :--- | :--- | :--- | :--- | :--- |
| **R1: Redis Session** | `backend/app/services/state_store.py`<br>`backend/app/services/sessions.py`<br>`backend/app/models/state.py` | `StateStore` (SQLite) がセッション(`SessionRecord`)、ログイン(`AuthSessionRecord`)、ジョブ(`JobRecord`)を永続化。 | SQLite から Redis への移行。`StateStore` の責務分割（Persistent vs Volatile）。mTLS 証明書の一時保存先検討（Redis or Volume）。 | Missing |
| **R2: Worker Async** | `backend/app/services/sessions.py` (`execute_command`)<br>`backend/app/services/state_store.py` | `execute_command` 内で `asyncio.create_task` を使用し、プロセス内で実行・状態管理。 | タスクキュー（Redis List/Stream 等）の導入。コンシューマーとなる Worker サービスの新規作成。ジョブ状態の Redis 管理。 | Missing |
| **R3: Secret Cache** | `backend/app/services/secrets.py` (`SecretManager`) | `self._cache` (Python dict) によるメモリ内キャッシュ。 | Redis をバックエンドとするキャッシュ機構への変更。 | Missing |
| **R4: Log Sanitize** | `backend/app/main.py`<br>`logging` config | `main.py` でリクエストボディの単純な切り捨て/非表示のみ実装。 | ログ出力時のフィルタリング層（Formatter/Filter）。機密情報のパターンマッチ・マスク処理。 | Missing |
| **R5: Key Fail Fast** | `backend/app/config.py` (`Settings`) | キー未設定時に自動生成してファイル保存するフォールバックロジックが存在。 | Production モード時の自動生成廃止・起動停止ロジック。 | Modification |
| **R6: SSRF** | `backend/app/services/catalog.py`<br>`backend/app/services/state_store.py` | スキームと `REMOTE_MCP_ALLOWED_DOMAINS` による簡易チェックのみ。 | プライベート IP（10.x, 172.16.x, 192.168.x）、Link-Local、Loopback の厳密な解決とブロックロジック。 | Missing |
| **R7: Config/Secret** | `backend/app/services/state_store.py` | 明確な分離境界が曖昧。一部 `CredentialRecord` 等で混在の可能性。 | 永続化対象（Config）と揮発対象（Secrets）の明確なモデル分離と保存先（SQLite vs Redis）の使い分け。 | Refactor |
| **R8: DevContainer** | N/A | 存在しない。 | `.devcontainer` 定義、マルチコンテナ構成（Backend, Frontend, Redis, Worker）の定義。 | Missing |
| **R9: Compatibility** | `backend/app/api/` | 既存 API エンドポイント。 | API コントラクトの維持。Redis 移行に伴う内部ロジック変更の影響遮断。 | Constraint |

## 3. Implementation Approach Options

### Option A: Extend Existing Components (StateStore 拡張)
既存の `StateStore` クラス内に Redis クライアントを追加し、データ種別（セッションか設定か）に応じて保存先を振り分けるロジックを埋め込む。

- **Pros**: 呼び出し元（Service層）の変更を最小限に抑えられる。
- **Cons**: `StateStore` が肥大化し、単一責任の原則（SRP）に違反する。SQLite と Redis の接続管理が混在し複雑化する。Worker からの参照も複雑になる。
- **Trade-offs**: 初期実装は早いが、保守性とスケーラビリティが低い。

### Option B: Create New Components (Layer Separation)
`StateStore` は SQLite (Config/Audit) 専用とし、新たに `SessionStore` / `JobQueue` (Redis) クラスを作成する。Service 層は用途に応じてこれらを使い分ける。Worker は独立したエントリポイントを持つ。

- **Pros**: 責務が明確（永続化 vs 揮発性）。Worker の実装が切り出しやすい。テストが容易。
- **Cons**: Service 層の多くの箇所で依存関係の書き換えが必要（`StateStore` への依存を `SessionStore` へ変更など）。
- **Trade-offs**: リファクタリング規模は大きいが、長期的な品質が高い。

### Option C: Hybrid Approach (Recommendation)
Option B を基本としつつ、段階的に移行する。まず `RedisService` を導入し、`SecretManager` と `SessionService` (の内部) から利用開始する。`StateStore` からセッション関連メソッドを削除・移行し、インターフェースを整理する。

- **Rationale**: 既存機能への影響をコントロールしながら、確実にステートレス化を進められる。

## 4. Implementation Complexity & Risk

- **Effort**: **XL (2+ weeks)**
  - Redis 導入、Worker コンテナ追加、SSRF 対策、DevContainer 整備と広範囲に及ぶため。特に非同期ジョブ基盤の構築とテストに工数を要する。
- **Risk**: **Medium**
  - 技術スタック自体（Redis/Celery等）は標準的だが、既存の認証・セッション管理ロジックを置き換えるため、リグレッションのリスクがある。特に mTLS 証明書の扱いや Bitwarden 連携部分の挙動維持に注意が必要。

## 5. Recommendations for Design Phase

### Preferred Approach
**Option B/C (Component Separation)** を採用すべきである。
1. **Infrastructure**: Redis コンテナと Worker コンテナを `docker-compose.yml` に追加。
2. **Data Layer**:
    - `PersistentStore` (SQLite): ユーザー設定、カタログキャッシュ（永続化する場合）、監査ログ。
    - `VolatileStore` (Redis): セッション、認証トークン、Bitwarden キャッシュ、ジョブキュー。
3. **Security**: `SecurityService` またはユーティリティを作成し、SSRF チェックやログサニタイズを集約。
4. **Worker**: `backend/worker/` または `backend/app/worker.py` を作成し、バックエンドとコードベースを共有しつつエントリーポイントを分ける。

### Research Items (To Carry Forward)
- **Research Needed**: mTLS 証明書（ファイル）の Redis への保存方法、または Redis を使わず Volume共有で対応するかの決定（ステートレス化の観点では Redis/DB 保存または動的生成が望ましい）。
- **Research Needed**: Worker コンテナでの Bitwarden CLI 利用方法（セッションキーの共有方法、CLI バイナリの配置）。
- **Research Needed**: Python における堅牢な SSRF 対策ライブラリまたは実装パターン（`ipaddress` モジュールの適用範囲検証）。

## 6. Document Status
- [x] Gap Analysis Executed
- [x] Options Evaluated
- [x] Risk Assessed
