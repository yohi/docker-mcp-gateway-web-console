# Technical Design Document

## Feature: Gateway Console Refactoring

**Version**: 1.0  
**Created**: 2025-12-18  
**Language**: ja

---

## 1. Overview

本設計書は、`docker-mcp-gateway-web-console` の大規模リファクタリングに関する技術設計を定義する。主な目的は以下の通り:

1. **ステートレス化**: Redis を用いたセッション管理により、バックエンドの水平スケーリングを可能にする
2. **非同期処理**: ARQ (Asynchronous Redis Queue) を用いた Worker コンテナで Bitwarden 操作等の重い処理を非同期化
3. **セキュリティ強化**: ログサニタイズ、SSRF 対策、暗号化キー管理の厳格化
4. **開発環境標準化**: DevContainer による統合開発環境の提供

### Requirements Traceability

| Requirement ID | Requirement Title | Design Section |
|----------------|-------------------|----------------|
| 1.1-1.4 | Redis によるセッション永続化 | 3.1 RedisService, 4.1 Session Management |
| 2.1-2.4 | Worker による非同期処理 | 3.2 JobQueue, 3.3 WorkerService |
| 3.1-3.4 | SecretManager キャッシュ移行 | 3.1 RedisService, 4.2 Secret Cache |
| 4.1-4.4 | ログサニタイズ | 3.4 LogSanitizer |
| 5.1-5.4 | 暗号化キー管理 | 3.5 KeyManager |
| 6.1-6.4 | SSRF 対策 | 3.6 UrlValidator |
| 7.1-7.4 | Config/Secrets 分離 | 4.3 Data Model Separation |
| 8.1-8.4 | DevContainer | 5. Infrastructure |
| 9.1-9.3 | 後方互換性 | 6. Migration Strategy |

---

## 2. Architecture Pattern & Boundary Map

### 2.1 High-Level Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Docker Compose                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │   Frontend   │    │   Backend    │    │    Worker    │    │   Redis   │ │
│  │  (Next.js)   │◄──►│  (FastAPI)   │◄──►│    (ARQ)     │◄──►│           │ │
│  │   :3000      │    │   :8000      │    │              │    │   :6379   │ │
│  └──────────────┘    └──────┬───────┘    └──────┬───────┘    └───────────┘ │
│                             │                   │                           │
│                             ▼                   ▼                           │
│                      ┌──────────────┐    ┌──────────────┐                   │
│                      │   SQLite     │    │ Bitwarden CLI│                   │
│                      │  (state.db)  │    │              │                   │
│                      └──────────────┘    └──────────────┘                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow Boundaries

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Service Layer                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ AuthService │  │SessionService│ │SecretManager│  │CatalogService│        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │                │
├─────────┼────────────────┼────────────────┼────────────────┼────────────────┤
│         │                │                │                │                │
│  ┌──────▼────────────────▼────────────────▼──────┐  ┌──────▼──────┐        │
│  │              RedisService                      │  │ StateStore  │        │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐    │  │  (SQLite)   │        │
│  │  │ Sessions │  │  Cache   │  │ JobQueue │    │  │             │        │
│  │  └──────────┘  └──────────┘  └──────────┘    │  │ - Config    │        │
│  └───────────────────────┬───────────────────────┘  │ - Audit     │        │
│                          │                          │ - Credentials│        │
│                          ▼                          └──────────────┘        │
│                       Redis                                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Storage Responsibility Matrix

| データ種別 | 保存先 | TTL | 暗号化 |
|-----------|--------|-----|--------|
| AuthSession (ログインセッション) | Redis | SESSION_TIMEOUT_MINUTES | No (セッションキーは暗号化済み) |
| GatewaySession (実行セッション) | Redis | idle_deadline | No |
| JobRecord (ジョブ状態) | Redis (ARQ) | JOB_RETENTION_HOURS | No |
| SecretCache (Bitwarden キャッシュ) | Redis | SESSION_TIMEOUT_MINUTES | Yes (Fernet) |
| mTLS Certificate Bundle | 共有ボリューム（data/certs） | セッション TTL | ファイル権限 (0600) |
| CredentialRecord (OAuth トークン) | SQLite | CREDENTIAL_RETENTION_DAYS | Yes (Fernet) |
| ContainerConfig | SQLite | 永続 | No |
| AuditLog | SQLite | 永続 | No |
| SignaturePolicy | SQLite | 永続 | No |
| GatewayAllowEntry | SQLite | 永続 | No |

---

## 3. Components & Interface Contracts

### 3.1 RedisService

**責務**: Redis への接続管理、セッション・キャッシュ・ジョブ状態の CRUD 操作

**Location**: `backend/app/services/redis_service.py`

```python
from typing import Optional, Dict, Any
from datetime import timedelta
import redis.asyncio as redis

class RedisService:
    """Redis 接続とセッション/キャッシュ操作を提供する。"""

    def __init__(self, redis_url: str) -> None:
        """Redis クライアントを初期化する。"""
        ...

    async def connect(self) -> None:
        """Redis への接続を確立する。"""
        ...

    async def disconnect(self) -> None:
        """Redis 接続を閉じる。"""
        ...

    async def health_check(self) -> bool:
        """Redis の疎通確認を行う。"""
        ...

    # Session Operations
    async def save_auth_session(
        self,
        session_id: str,
        data: Dict[str, Any],
        ttl: timedelta,
    ) -> None:
        """認証セッションを保存する。"""
        ...

    async def get_auth_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """認証セッションを取得する。"""
        ...

    async def delete_auth_session(self, session_id: str) -> None:
        """認証セッションを削除する。"""
        ...

    async def extend_session_ttl(self, session_id: str, ttl: timedelta) -> bool:
        """セッションの TTL を延長する。"""
        ...

    # Cache Operations
    async def set_cache(
        self,
        key: str,
        value: str,
        ttl: timedelta,
        namespace: str = "cache",
    ) -> None:
        """キャッシュを設定する。"""
        ...

    async def get_cache(self, key: str, namespace: str = "cache") -> Optional[str]:
        """キャッシュを取得する。"""
        ...

    async def delete_cache_by_prefix(self, prefix: str) -> int:
        """プレフィックスに一致するキャッシュを削除する。"""
        ...

    # mTLS 証明書は共有ボリューム（data/certs）にファイルとして保存し、RedisService の責務外とする
```

**Key Design Decisions**:
- `redis.asyncio` を使用し、FastAPI の非同期処理と統合
- セッションデータは JSON シリアライズして Hash に保存
- キー命名規則: `{namespace}:{entity_type}:{id}` (例: `session:auth:abc123`)

### 3.2 JobQueue

**責務**: ARQ を用いたジョブのエンキュー、状態管理

**Location**: `backend/app/services/job_queue.py`

```python
from typing import Optional, Dict, Any, List
from datetime import datetime
from arq import ArqRedis
from arq.jobs import Job

class JobStatus:
    """ジョブ状態の表現。"""
    job_id: str
    status: str  # queued | running | succeeded | failed
    result: Optional[Any]
    error: Optional[str]
    queued_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

class JobQueue:
    """ARQ ベースのジョブキュー操作を提供する。"""

    def __init__(self, redis_pool: ArqRedis) -> None:
        """ARQ Redis プールを受け取る。"""
        ...

    async def enqueue_bitwarden_resolve(
        self,
        session_id: str,
        item_id: str,
        field: str,
        bw_session_key: str,
    ) -> str:
        """Bitwarden 解決ジョブをエンキューし、job_id を返す。"""
        ...

    async def enqueue_container_exec(
        self,
        session_id: str,
        container_id: str,
        command: List[str],
        max_run_seconds: int,
        output_bytes_limit: int,
    ) -> str:
        """コンテナ実行ジョブをエンキューし、job_id を返す。"""
        ...

    async def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """ジョブの状態を取得する。"""
        ...

    async def cancel_job(self, job_id: str) -> bool:
        """ジョブをキャンセルする（可能な場合）。"""
        ...
```

### 3.3 WorkerService

**責務**: ARQ Worker のエントリポイント、ジョブハンドラの定義

**Location**: `backend/app/worker.py`

```python
from arq import cron
from arq.connections import RedisSettings
from app.services.secrets import SecretManager
from app.services.containers import ContainerService

async def resolve_bitwarden_secret(
    ctx: dict,
    session_id: str,
    item_id: str,
    field: str,
    bw_session_key: str,
) -> dict:
    """Bitwarden からシークレットを解決する。"""
    ...

async def execute_container_command(
    ctx: dict,
    session_id: str,
    container_id: str,
    command: list,
    max_run_seconds: int,
    output_bytes_limit: int,
) -> dict:
    """コンテナ内でコマンドを実行する。"""
    ...

async def cleanup_expired_sessions(ctx: dict) -> int:
    """期限切れセッションをクリーンアップする（定期タスク）。"""
    ...

class WorkerSettings:
    """ARQ Worker 設定。"""
    functions = [
        resolve_bitwarden_secret,
        execute_container_command,
    ]
    cron_jobs = [
        cron(cleanup_expired_sessions, hour={0, 6, 12, 18}, minute=0),
    ]
    redis_settings = RedisSettings()
    max_jobs = 10
    job_timeout = 300  # 5 minutes
```

**Worker 起動コマンド**:
```bash
arq app.worker.WorkerSettings
```

### 3.4 LogSanitizer

**責務**: ログ出力時の機密情報マスク処理

**Location**: `backend/app/services/log_sanitizer.py`

```python
import logging
import re
from typing import Dict, List, Pattern

class SanitizingFilter(logging.Filter):
    """ログレコードから機密情報をマスクするフィルタ。"""

    SENSITIVE_PATTERNS: List[Pattern] = [
        re.compile(r'"password"\s*:\s*"[^"]*"', re.IGNORECASE),
        re.compile(r'"token"\s*:\s*"[^"]*"', re.IGNORECASE),
        re.compile(r'"api_key"\s*:\s*"[^"]*"', re.IGNORECASE),
        re.compile(r'"secret"\s*:\s*"[^"]*"', re.IGNORECASE),
        re.compile(r'"bw_session_key"\s*:\s*"[^"]*"', re.IGNORECASE),
        re.compile(r'"master_password"\s*:\s*"[^"]*"', re.IGNORECASE),
        re.compile(r'Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+'),
    ]
    MASK = '"***REDACTED***"'

    def filter(self, record: logging.LogRecord) -> bool:
        """ログメッセージをサニタイズする。"""
        ...

class SensitiveEndpointFilter(logging.Filter):
    """機密エンドポイントへのリクエストボディをログから除外するフィルタ。"""

    SENSITIVE_PATHS: List[str] = [
        "/api/auth/login",
        "/api/auth/logout",
        "/api/github-token",
        "/api/catalog/oauth",
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """機密パスへのリクエストボディを除外する。"""
        ...

def configure_logging() -> None:
    """アプリケーションログにサニタイズフィルタを適用する。"""
    ...
```

### 3.5 KeyManager

**責務**: 暗号化キーの検証と Fail Fast 起動制御

**Location**: `backend/app/services/key_manager.py`

**Key Policy**:

- 暗号化キーは **全環境で必須** とし、**自動生成** や **ファイル保存** は行わない。
- 起動時に `OAUTH_TOKEN_ENCRYPTION_KEY` が未設定または不正な場合は起動を中止する（Fail Fast）。
- 既存実装の `backend/app/config.py` にある env>file>generate のフォールバックは削除する。

```python
from typing import Optional
from cryptography.fernet import Fernet

class KeyValidationError(Exception):
    """暗号化キーの検証エラー。"""
    pass

class KeyManager:
    """暗号化キーの管理と検証を行う。"""

    REQUIRED_KEYS = [
        "OAUTH_TOKEN_ENCRYPTION_KEY",
    ]

    def __init__(self, environment: str = "development") -> None:
        """環境プロファイルを設定する。"""
        ...

    def validate_keys(self) -> None:
        """
        必須の暗号化キーを検証する。

        Raises:
            KeyValidationError: 必須キーが未設定または不正の場合
        """
        ...

    def get_fernet(self, key_name: str) -> Fernet:
        """指定されたキー名の Fernet インスタンスを返す。"""
        ...

    @staticmethod
    def is_valid_fernet_key(key: str) -> bool:
        """Fernet キーの形式を検証する。"""
        ...
```

**Fail Fast 実装**:
```python
# backend/app/main.py
from app.services.key_manager import KeyManager, KeyValidationError

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 全環境で暗号化キーを検証
    environment = os.getenv("ENVIRONMENT", "development")
    key_manager = KeyManager(environment=environment)
    try:
        key_manager.validate_keys()
    except KeyValidationError as e:
        logger.critical("暗号化キーの検証に失敗しました: %s", e)
        raise SystemExit(1)
    
    yield
```

### 3.6 UrlValidator

**責務**: SSRF 対策のための URL 検証

**Location**: `backend/app/services/url_validator.py`

```python
from typing import List, Tuple, Optional
from ipaddress import ip_address, IPv4Address, IPv6Address
from urllib.parse import urlparse
import socket

class UrlValidationError(Exception):
    """URL 検証エラー。"""
    def __init__(self, message: str, reason_code: str) -> None:
        self.message = message
        self.reason_code = reason_code
        super().__init__(message)

class UrlValidator:
    """SSRF 対策のための URL 検証を行う。"""

    BLOCKED_METADATA_IPS = [
        "169.254.169.254",  # AWS/GCP/Azure metadata
        "fd00:ec2::254",    # AWS IMDSv2 IPv6
    ]

    def __init__(self, allow_insecure: bool = False) -> None:
        """
        Args:
            allow_insecure: True の場合、localhost への HTTP を許可
        """
        self.allow_insecure = allow_insecure

    def validate_url(self, url: str) -> None:
        """
        URL を検証し、SSRF リスクがある場合は例外を送出する。

        Raises:
            UrlValidationError: 検証失敗時
        """
        parsed = urlparse(url)

        # スキーム検証
        self._validate_scheme(parsed.scheme)

        # ホスト名解決と IP 検証
        if parsed.hostname:
            self._resolve_and_validate_host(parsed.hostname)

    def _validate_scheme(self, scheme: str) -> None:
        """スキームを検証する。"""
        if scheme not in ("http", "https"):
            raise UrlValidationError(
                f"Unsupported scheme: {scheme}",
                "invalid_scheme"
            )

    def _resolve_and_validate_host(self, hostname: str) -> List[str]:
        """
        ホスト名を DNS 解決し、全 IP アドレスを検証する。
        A/AAAA 両方のレコードを解決し、すべての IP を検証する。

        Args:
            hostname: 解決するホスト名

        Returns:
            解決された IP アドレスのリスト（すべて検証済み）

        Raises:
            UrlValidationError: いずれかの IP がブロック対象の場合
        """
        resolved_ips: List[str] = []

        # A レコード (IPv4) を解決
        try:
            ipv4_results = socket.getaddrinfo(
                hostname, None, socket.AF_INET, socket.SOCK_STREAM
            )
            for result in ipv4_results:
                ip = result[4][0]
                if ip not in resolved_ips:
                    resolved_ips.append(ip)
        except socket.gaierror:
            pass  # IPv4 レコードが存在しない場合は無視

        # AAAA レコード (IPv6) を解決
        try:
            ipv6_results = socket.getaddrinfo(
                hostname, None, socket.AF_INET6, socket.SOCK_STREAM
            )
            for result in ipv6_results:
                ip = result[4][0]
                if ip not in resolved_ips:
                    resolved_ips.append(ip)
        except socket.gaierror:
            pass  # IPv6 レコードが存在しない場合は無視

        if not resolved_ips:
            raise UrlValidationError(
                f"Failed to resolve hostname: {hostname}",
                "dns_resolution_failed"
            )

        # すべての IP アドレスを検証
        for ip in resolved_ips:
            is_blocked, reason = self._is_blocked_ip(ip)
            if is_blocked:
                raise UrlValidationError(
                    f"Blocked IP address {ip} ({reason}) for hostname {hostname}",
                    reason
                )

        return resolved_ips

    def _is_blocked_ip(self, ip: str) -> Tuple[bool, str]:
        """
        IP アドレスがブロック対象かを判定する。
        IPv6 の正規化を行い、テキスト表現の違いを吸収する。

        Args:
            ip: 検証する IP アドレス文字列

        Returns:
            (blocked, reason) のタプル
        """
        addr = ip_address(ip)

        if addr.is_private:
            return True, "private_ip"
        if addr.is_loopback:
            return True, "loopback"
        if addr.is_link_local:
            return True, "link_local"
        if addr.is_reserved:
            return True, "reserved"
        if addr.is_multicast:
            return True, "multicast"

        # メタデータエンドポイントのチェック（正規化して比較）
        for blocked_ip in self.BLOCKED_METADATA_IPS:
            blocked_addr = ip_address(blocked_ip)
            if addr == blocked_addr:
                return True, "metadata_endpoint"

        return False, ""

    def validate_and_connect(
        self, url: str, timeout: float = 5.0
    ) -> Tuple[List[str], socket.socket]:
        """
        TOCTOU 対策: URL を検証し、検証済み IP で即座に接続する。

        この関数は DNS 解決、検証、接続を原子的に実行し、
        検証後の DNS 変更リスクを最小化する。

        Args:
            url: 接続先 URL
            timeout: 接続タイムアウト秒数

        Returns:
            (resolved_ips, connected_socket) のタプル

        Raises:
            UrlValidationError: 検証失敗時
            socket.error: 接続失敗時
        """
        parsed = urlparse(url)

        # スキーム検証
        self._validate_scheme(parsed.scheme)

        if not parsed.hostname:
            raise UrlValidationError("Missing hostname", "invalid_url")

        # DNS 解決と IP 検証
        resolved_ips = self._resolve_and_validate_host(parsed.hostname)

        # 検証済み IP で即座に接続（最初の IP を使用）
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        sock = socket.socket(
            socket.AF_INET6 if ":" in resolved_ips[0] else socket.AF_INET,
            socket.SOCK_STREAM
        )
        sock.settimeout(timeout)

        try:
            sock.connect((resolved_ips[0], port))
            return resolved_ips, sock
        except Exception:
            sock.close()
            raise
```

**TOCTOU (Time-of-Check-Time-of-Use) 対策**:

URL 検証には以下の 2 つの使用パターンがあります:

1. **標準的な検証**: `validate_url()` を使用
   - DNS 解決と IP 検証を行う
   - 呼び出し元は接続前に再検証する責任がある
   - 検証から接続までの間に DNS が変更されるリスクが残る

2. **安全な接続**: `validate_and_connect()` を使用（推奨）
   - DNS 解決、検証、接続を原子的に実行
   - 検証済み IP で即座に接続するため TOCTOU リスクを最小化
   - HTTP クライアントでこのソケットを再利用可能

使用例:
```python
# パターン 1: 標準的な検証（TOCTOU リスクあり）
validator = UrlValidator()
validator.validate_url("https://example.com/image.png")
# ... 接続処理（別途実装）

# パターン 2: 安全な接続（推奨）
validator = UrlValidator()
resolved_ips, sock = validator.validate_and_connect("https://example.com/image.png")
# sock を使用して HTTP リクエストを送信
sock.close()
```

**セキュリティ上の注意**:
- DNS レスポンスはキャッシュされる可能性があるため、長時間接続を保持する場合は定期的な再検証を検討する
- IPv6 の正規化により、`fd00:ec2::254` と `fd00:ec2::0:0:0:254` などの表記ゆれを吸収する
- すべての解決された IP（A および AAAA レコード）を検証し、いずれか一つでもブロック対象なら例外を送出する

---

## 4. Data Flow & Integration

### 4.1 Session Management Flow

```text
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │     │  Backend │     │  Redis   │     │ Bitwarden│
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │
     │ POST /auth/login               │                │
     │ {email, api_key}               │                │
     │───────────────►│                │                │
     │                │                │                │
     │                │ bw unlock      │                │
     │                │────────────────────────────────►│
     │                │                │                │
     │                │◄───────────────────────────────│
     │                │ bw_session_key │                │
     │                │                │                │
     │                │ HSET session:auth:{id}         │
     │                │ {user_email, bw_session_key, ...}
     │                │───────────────►│                │
     │                │                │                │
     │                │ EXPIRE session:auth:{id} TTL   │
     │                │───────────────►│                │
     │                │                │                │
     │◄───────────────│                │                │
     │ {session_id, expires_at}       │                │
     │                │                │                │
```

### 4.2 Async Job Flow (Bitwarden Resolve)

```text
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │     │  Backend │     │  Redis   │     │  Worker  │     │ Bitwarden│
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │                │
     │ POST /api/containers/install?async=true        │                │
     │ {env: {"API_KEY": "{{bw:...}}"}}                │                │
     │───────────────►│                │                │                │
     │                │                │                │                │
     │                │ LPUSH arq:queue:default        │                │
     │                │ {job_id, task, args}           │                │
     │                │───────────────►│                │                │
     │                │                │                │                │
     │◄───────────────│                │                │                │
     │ {job_id, status: "queued"}     │                │                │
     │                │                │                │                │
     │                │                │ BRPOP arq:queue:default        │
     │                │                │◄──────────────│                │
     │                │                │                │                │
     │                │                │                │ bw get item   │
     │                │                │                │───────────────►│
     │                │                │                │                │
     │                │                │                │◄───────────────│
     │                │                │                │ secret_value   │
     │                │                │                │                │
     │                │                │ HSET arq:result:{job_id}       │
     │                │                │◄──────────────│                │
     │                │                │                │                │
     │ GET /api/jobs/{job_id}         │                │                │
     │───────────────►│                │                │                │
     │                │                │                │                │
     │                │ HGET arq:result:{job_id}       │                │
     │                │───────────────►│                │                │
     │                │                │                │                │
     │◄───────────────│                │                │                │
     │ {status: "succeeded", result: ...}              │                │
     │                │                │                │                │
```

### 4.3 Data Model Separation

**Volatile Data (Redis)**:
```python
# backend/app/models/volatile.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any

class RedisAuthSession(BaseModel):
    """Redis に保存する認証セッション。"""
    session_id: str
    user_email: str
    bw_session_key: str  # 暗号化済み
    created_at: datetime
    last_activity: datetime

class RedisGatewaySession(BaseModel):
    """Redis に保存するゲートウェイセッション。"""
    session_id: str
    server_id: str
    container_id: str
    config: Dict[str, Any]
    state: str
    idle_deadline: datetime

# mTLS 証明書は共有ボリューム（data/certs）へファイルとして保存し、セッションレコードにはパス参照を保持する

class RedisSecretCache(BaseModel):
    """Redis に保存するシークレットキャッシュ。"""
    cache_key: str  # {session_id}:{item_id}:{field}
    value: str      # 暗号化済み
```

**Persistent Data (SQLite)** - 既存の `StateStore` を維持:
```python
# backend/app/models/state.py (既存、変更なし)
class CredentialRecord(BaseModel): ...
class ContainerConfigRecord(BaseModel): ...
class SignaturePolicyRecord(BaseModel): ...
class GatewayAllowEntry(BaseModel): ...
class AuditLogEntry(BaseModel): ...
```

---

## 5. Technology Stack & Alignment

### 5.1 New Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `redis[hiredis]` | ==5.0.8 | Redis 非同期クライアント (CVE-2024-31449 修正済み) |
| `arq` | ==0.26.1 | asyncio ネイティブタスクキュー (安定版パッチリリース) |

**requirements.txt 追加**:
```text
redis[hiredis]==5.0.8
arq==0.26.1
```

### 5.2 Infrastructure Changes

**docker-compose.yml 追加サービス**:
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - mcp-gateway

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    command: arq app.worker.WorkerSettings
    volumes:
      - ./backend:/app
      - ./data:/app/data
      - ${DOCKER_SOCKET_PATH:-/run/user/${UID:-1000}/docker.sock}:${DOCKER_SOCKET_PATH:-/run/user/${UID:-1000}/docker.sock}
      - "bw-cli-config:/root/.config/Bitwarden CLI"
      - "bw-cli-cache:/root/.cache/Bitwarden CLI"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - BITWARDEN_CLI_PATH=/usr/local/bin/bw
      - DOCKER_HOST=${DOCKER_HOST:-unix:///run/user/${UID:-1000}/docker.sock}
    depends_on:
      - redis
    networks:
      - mcp-gateway

volumes:
  redis-data:
```

### 5.3 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Redis 接続 URL |
| `ENVIRONMENT` | No | `development` | 環境プロファイル (`development` / `production`) |
| `OAUTH_TOKEN_ENCRYPTION_KEY` | Yes | - | Fernet 暗号化キー（全環境で必須） |

開発環境でも `OAUTH_TOKEN_ENCRYPTION_KEY` は必須とし、`.env.example`（または DevContainer の環境設定）で供給する。

---

## 6. Migration Strategy

### 6.1 Phase 1: Infrastructure (Week 1)

1. Redis コンテナを `docker-compose.yml` に追加
2. `RedisService` を実装し、接続テストを作成
3. `KeyManager` を実装し、Fail Fast ロジックを追加
4. `LogSanitizer` を実装し、既存ログ設定に適用

### 6.2 Phase 2: Session Migration (Week 1-2)

1. `AuthService` を `RedisService` に移行
   - `StateStore.save_auth_session` → `RedisService.save_auth_session`
   - 既存 API コントラクトは維持
2. `SessionService` を `RedisService` に移行
   - mTLS 証明書は共有ボリューム（data/certs）へファイルとして保存し、セッションレコードにはファイルパス参照を保持する
3. 既存の SQLite セッションテーブルは読み取り専用で維持（フォールバック）

### 6.3 Phase 3: Worker & Async Jobs (Week 2)

1. `WorkerService` と `JobQueue` を実装
2. `SecretManager` を Redis キャッシュに移行
3. `SessionService.execute_command` を非同期ジョブに変更
4. Worker コンテナを追加

### 6.4 Phase 4: Security Hardening (Week 2-3)

1. `UrlValidator` を実装し、`CatalogService` に適用
2. SSRF 対策のテストケースを追加
3. ログサニタイズの網羅性を検証

### 6.5 Phase 5: DevContainer (Week 3)

1. `.devcontainer/devcontainer.json` を作成
2. マルチコンテナ構成を定義
3. 開発者向けドキュメントを更新

---

## 7. API Contract Compatibility

### 7.1 Unchanged Endpoints

以下のエンドポイントは、リクエスト/レスポンス構造を変更しない:

- `POST /api/auth/login` - LoginRequest/LoginResponse
- `POST /api/auth/logout` - LogoutResponse
- `GET /api/auth/session` - SessionValidationResponse
- `GET /api/catalog` - CatalogResponse
- `GET /api/containers` - ContainerListResponse
- `POST /api/containers` - ContainerCreateResponse
- `POST /api/containers/install` - ContainerInstallResponse
- `POST /api/containers/{id}/start` - ContainerActionResponse
- `POST /api/containers/{id}/stop` - ContainerActionResponse
- `GET /api/inspector/{id}` - InspectorResponse

### 7.2 New Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs/{job_id}` | GET | ジョブ状態の取得 |
| `/health/redis` | GET | Redis ヘルスチェック |

`GET /api/jobs/{job_id}` は Authorization 必須とし、ジョブの所有者（セッションID）が呼び出し元と一致する場合のみ結果を返す。
一致しない（または存在しない）場合は `JOB_NOT_FOUND`（404）を返し、情報漏えいを防ぐ。

### 7.3 Modified Behavior (Internal Only)

- `POST /api/containers` および `POST /api/containers/install`（Bitwarden 参照を含む場合）:
  - **Default (互換維持)**: 従来通り同期で解決し、HTTP 201 + 既存レスポンス（ContainerCreateResponse/ContainerInstallResponse）を返す
  - **Opt-in Async**: `async=true` を指定した場合のみ、HTTP 202 + `job_id` を返す
  - クライアントは `GET /api/jobs/{job_id}` で状態と結果（成功時は `container_id` 等、失敗時は秘密情報を含まない理由）を取得する
  - Backend は `GET /api/jobs/{job_id}` 実行時にセッション検証と所有権検証を行い、他セッションの結果を返さない

---

## 8. Testing Strategy

### 8.1 Unit Tests

| Component | Test File | Coverage Target |
|-----------|-----------|-----------------|
| RedisService | `tests/test_redis_service.py` | 90% |
| JobQueue | `tests/test_job_queue.py` | 85% |
| LogSanitizer | `tests/test_log_sanitizer.py` | 95% |
| KeyManager | `tests/test_key_manager.py` | 95% |
| UrlValidator | `tests/test_url_validator.py` | 95% |

### 8.2 Integration Tests

| Scenario | Test File |
|----------|-----------|
| Redis セッション CRUD | `tests/integration/test_redis_session.py` |
| ARQ ジョブ実行 | `tests/integration/test_arq_jobs.py` |
| SSRF 対策検証 | `tests/integration/test_ssrf_protection.py` |

### 8.3 E2E Tests

| Scenario | Test File |
|----------|-----------|
| ログイン → コンテナ起動 → ログアウト | `frontend/e2e/session-flow.spec.ts` |
| 非同期ジョブ完了待ち | `frontend/e2e/async-job.spec.ts` |

---

## 9. Appendix

### 9.1 Redis Key Schema

```text
session:auth:{session_id}          # Hash: 認証セッション
session:gateway:{session_id}       # Hash: ゲートウェイセッション
cache:secret:{session_id}:{key}    # String: シークレットキャッシュ
arq:queue:default                  # List: ジョブキュー
arq:result:{job_id}                # Hash: ジョブ結果
```

 mTLS 証明書は Redis ではなく共有ボリューム（`data/certs/{session_id}/`）へ保存する。

### 9.2 Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `REDIS_UNAVAILABLE` | 503 | Redis 接続エラー |
| `JOB_NOT_FOUND` | 404 | ジョブが存在しない |
| `JOB_TIMEOUT` | 408 | ジョブがタイムアウト |
| `SSRF_BLOCKED` | 400 | SSRF 対策によりブロック |
| `KEY_VALIDATION_FAILED` | 500 | 暗号化キー検証失敗 |

### 9.3 References

- [ARQ Documentation](https://arq-docs.helpmanual.io/)
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [Python ipaddress Module](https://docs.python.org/3/library/ipaddress.html)
- [Redis Async Python](https://redis.io/docs/clients/python/)
