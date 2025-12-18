# Research Log: Gateway Console Refactoring

## Summary

本リサーチでは、`gateway-console-refactoring` の技術設計に必要な外部技術調査を実施した。主な調査対象は以下の通り:

1. **Redis セッション管理**: FastAPI における Redis セッション管理のベストプラクティス
2. **タスクキュー選定**: Celery vs ARQ (Asynchronous Redis Queue) の比較
3. **SSRF 対策**: Python `ipaddress` モジュールを用いたプライベート IP 検出と OWASP ガイドライン

## Research Log

### Topic 1: FastAPI + Redis セッション管理

**Sources**:
- [Upstash Redis Session Tutorial](https://upstash.com/docs/redis/tutorials/python_session)
- [fastapi-redis-session (PyPI)](https://pypi.org/project/fastapi-redis-session/)
- [starsessions + Redis Store](https://behainguyen.wordpress.com/2024/05/21/python-fastapi-implementing-persistent-stateful-http-sessions-with-redis-session-middleware-and-extending-oauth2passwordbearer-for-oauth2-security/)

**Findings**:
- `fastapi-redis-session` は軽量なライブラリで、`setSession` / `getSession` / `deleteSession` のシンプルな API を提供
- `starsessions` は Starlette ミドルウェアベースで、Redis Store をバックエンドに利用可能
- 本プロジェクトでは既存の認証フロー（Bitwarden セッションキー）があるため、ライブラリ依存よりも **直接 `redis-py` (async) を利用** し、既存の `AuthSessionRecord` / `SessionRecord` を Redis に保存する方式が適切

**Implications**:
- `redis[hiredis]` パッケージを `requirements.txt` に追加
- `RedisService` クラスを新規作成し、セッション CRUD を実装
- TTL を活用してセッションタイムアウトを Redis 側で管理

### Topic 2: タスクキュー選定 (Celery vs ARQ)

**Sources**:
- [Celery vs ARQ Comparison (Leapcell)](https://leapcell.io/blog/celery-versus-arq-choosing-the-right-task-queue-for-python-applications)
- [ARQ vs Celery (Bithost)](https://www.bithost.in/blog/tech-2/how-to-run-fastapi-background-tasks-arq-vs-celery-96)

**Findings**:

| 観点 | Celery | ARQ |
|------|--------|-----|
| **アーキテクチャ** | 同期ベース（prefork/eventlet/gevent） | asyncio ネイティブ |
| **ブローカー** | Redis, RabbitMQ, SQS 等 | Redis のみ |
| **依存関係** | 重い（多数の依存） | 軽量（redis のみ） |
| **FastAPI 親和性** | 中（別プロセス） | 高（同一イベントループ可） |
| **スケジューリング** | Celery Beat | cron 式サポート |
| **成熟度** | 非常に高い | 中程度 |

**Decision**:
- 本プロジェクトは FastAPI (asyncio) ベースであり、タスクは主に I/O バウンド（Bitwarden CLI 呼び出し、Docker 操作）
- **ARQ を採用**: 軽量、asyncio ネイティブ、Redis のみで完結
- Worker は `arq worker.WorkerSettings` で起動し、Backend と同一コードベースを共有

**Implications**:
- `arq` パッケージを `requirements.txt` に追加
- `backend/app/worker.py` を作成し、`WorkerSettings` を定義
- ジョブ状態は ARQ のビルトイン機能（Redis Hash/Sorted Set）で管理

### Topic 3: SSRF 対策

**Sources**:
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [Python ipaddress module](https://docs.python.org/3/library/ipaddress.html)
- [GeeksforGeeks: is_private](https://www.geeksforgeeks.org/python/python-program-to-determine-if-the-given-ip-address-is-public-or-private-using-ipaddress-module/)

**Findings**:
- OWASP は「ブロックリストアプローチ」を推奨（許可リストが不可能な場合）
- Python `ipaddress.ip_address(addr).is_private` で RFC 1918 プライベートアドレスを検出可能
- 追加で検出すべきアドレス:
  - `is_loopback`: 127.0.0.0/8, ::1
  - `is_link_local`: 169.254.0.0/16, fe80::/10
  - `is_reserved`: 予約済みアドレス
  - `is_multicast`: マルチキャストアドレス
- **DNS Rebinding 対策**: ドメイン名を解決後、全ての A/AAAA レコードを検証してからリクエストを送信

**Implications**:
- `SecurityService` または `url_validator.py` ユーティリティを作成
- URL 検証フロー:
  1. スキーム検証（HTTPS のみ、開発時は localhost HTTP 許可）
  2. ホスト名を DNS 解決
  3. 全 IP アドレスに対して `is_private`, `is_loopback`, `is_link_local`, `is_reserved` をチェック
  4. メタデータエンドポイント（169.254.169.254 等）を明示的にブロック
  5. リダイレクト無効化

## Architecture Pattern Evaluation

### Pattern: Repository + Service Layer with Dual Storage

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer (FastAPI)                       │
├─────────────────────────────────────────────────────────────────┤
│                        Service Layer                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ AuthService │  │SessionService│ │CatalogService│ ...         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
├─────────┼────────────────┼────────────────┼─────────────────────┤
│         │                │                │                      │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐              │
│  │ RedisService│  │  JobQueue   │  │ StateStore  │              │
│  │ (Volatile)  │  │   (ARQ)     │  │ (Persistent)│              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
├─────────┼────────────────┼────────────────┼─────────────────────┤
│         ▼                ▼                ▼                      │
│      Redis            Redis            SQLite                    │
└─────────────────────────────────────────────────────────────────┘
```

**Rationale**:
- 揮発性データ（セッション、キャッシュ、ジョブ）は Redis に集約
- 永続性データ（設定、監査ログ、資格情報暗号化済み）は SQLite に維持
- ARQ Worker は Redis を介してジョブを受信し、Backend と同一サービス層を利用

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| セッションストア | Redis (redis-py async) | ステートレス化、TTL 管理、スケーラビリティ |
| タスクキュー | ARQ | asyncio ネイティブ、軽量、Redis 統一 |
| SSRF 対策 | ipaddress + DNS 解決検証 | OWASP 準拠、標準ライブラリ活用 |
| 暗号化キー管理 | 環境変数必須 + Fail Fast | 自動生成廃止、Production 起動時検証 |
| DevContainer | docker-compose 拡張 | Backend/Worker/Frontend/Redis 統合 |

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Redis 障害時のサービス停止 | Medium | High | ヘルスチェック + 明確なエラーメッセージ + 復旧手順ドキュメント |
| ARQ Worker の Bitwarden CLI 連携 | Medium | Medium | セッションキーを Redis 経由で共有、CLI バイナリを Worker イメージに含める |
| DNS Rebinding 攻撃 | Low | High | 解決後 IP 検証、リダイレクト無効化 |
| 既存 API 互換性破壊 | Medium | High | API コントラクトテスト、段階的移行 |

## Open Questions

1. **mTLS 証明書の保存先**: Redis に Base64 エンコードで保存するか、共有ボリュームを使用するか？
   - **推奨**: Redis に保存（ステートレス化優先）、TTL をセッションと同期
2. **Worker スケーリング**: 複数 Worker インスタンスの競合制御は ARQ のビルトイン機能で十分か？
   - **推奨**: ARQ の `max_jobs` 設定で制御、初期は単一 Worker で検証
