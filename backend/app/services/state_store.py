"""SQLite ベースの永続化ストア実装。"""

import os
import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from ..config import settings
from ..models.state import (
    AuditLogEntry,
    AuthSessionRecord,
    ContainerConfigRecord,
    CredentialRecord,
    RemoteServerRecord,
    GatewayAllowEntry,
    JobRecord,
    GitHubTokenRecord,
    OAuthStateRecord,
    SessionRecord,
    SignaturePolicyRecord,
)

logger = logging.getLogger(__name__)


def _to_iso(dt: datetime) -> str:
    """datetime を ISO8601 文字列に変換する。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _from_iso(value: str) -> datetime:
    """ISO8601 文字列を datetime に変換する。"""
    return datetime.fromisoformat(value)


class StateStore:
    """永続化ストアのファサード。"""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or settings.state_db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        """SQLite 接続を取得する。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_schema(self) -> None:
        """必要なテーブルを作成する。既に存在する場合は何もしない。"""
        if self._initialized:
            return
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS credentials (
                    credential_key TEXT PRIMARY KEY,
                    token_ref TEXT NOT NULL,
                    scopes TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    server_id TEXT NOT NULL,
                    oauth_token_url TEXT,
                    oauth_client_id TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS remote_servers (
                    server_id TEXT PRIMARY KEY,
                    catalog_item_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    credential_key TEXT REFERENCES credentials(credential_key) ON DELETE SET NULL,
                    last_connected_at TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_remote_servers_catalog_item_id
                    ON remote_servers(catalog_item_id);
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state TEXT PRIMARY KEY,
                    server_id TEXT NOT NULL,
                    code_challenge TEXT,
                    code_challenge_method TEXT,
                    scopes TEXT NOT NULL,
                    authorize_url TEXT NOT NULL,
                    token_url TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    redirect_uri TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_oauth_states_expires_at
                    ON oauth_states(expires_at);
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    server_id TEXT NOT NULL,
                    config TEXT NOT NULL,
                    state TEXT NOT NULL,
                    idle_deadline TEXT NOT NULL,
                    gateway_endpoint TEXT NOT NULL,
                    metrics_endpoint TEXT NOT NULL,
                    mtls_cert_ref TEXT,
                    feature_flags TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    queued_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    exit_code INTEGER,
                    timeout INTEGER NOT NULL,
                    truncated INTEGER NOT NULL,
                    output_ref TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS signature_policies (
                    server_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS gateway_allowlist (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    version INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    target TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS github_tokens (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    token_ref TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_email TEXT NOT NULL,
                    bw_session_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_activity TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS container_configs (
                    container_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    image TEXT NOT NULL,
                    config TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._migrate_columns(conn)
            conn.commit()
        self._initialized = True

    def _migrate_columns(self, conn: sqlite3.Connection) -> None:
        """既存DBに対して不足カラムを追加する（軽量マイグレーション）。"""
        def _get_columns(table: str) -> set[str]:
            return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}

        try:
            credential_columns = _get_columns("credentials")
        except Exception:
            logger.debug("PRAGMA table_info failed; skipping migrations", exc_info=True)
            return

        statements: list[str] = []
        if "oauth_token_url" not in credential_columns:
            statements.append("ALTER TABLE credentials ADD COLUMN oauth_token_url TEXT")
        if "oauth_client_id" not in credential_columns:
            statements.append("ALTER TABLE credentials ADD COLUMN oauth_client_id TEXT")

        for stmt in statements:
            try:
                conn.execute(stmt)
            except Exception:
                logger.debug("Migration failed: %s", stmt, exc_info=True)

        self._migrate_audit_logs(conn)

    def _migrate_audit_logs(self, conn: sqlite3.Connection) -> None:
        """audit_logs テーブルを最新スキーマに再構築する。"""
        desired_columns = {
            "id",
            "category",
            "action",
            "actor",
            "target",
            "metadata",
            "created_at",
        }
        allowed_identifiers = {
            "id",
            "category",
            "action",
            "event_type",
            "actor",
            "target",
            "correlation_id",
            "metadata",
            "created_at",
        }
        try:
            audit_columns_raw = {
                row["name"] for row in conn.execute("PRAGMA table_info(audit_logs)").fetchall()
            }
        except Exception:
            logger.debug("PRAGMA table_info failed for audit_logs; skipping audit migrations", exc_info=True)
            return

        if not audit_columns_raw:
            return
        unexpected_columns = audit_columns_raw - allowed_identifiers
        if unexpected_columns:
            logger.debug("Ignoring unexpected audit_logs columns: %s", unexpected_columns)

        audit_columns = audit_columns_raw & allowed_identifiers

        if audit_columns_raw == desired_columns:
            return

        def _select_token(preferred: list[str], fallback_literal: str) -> str:
            for candidate in preferred:
                if candidate in audit_columns:
                    return candidate
            return fallback_literal

        select_id = _select_token(["id"], "NULL")
        select_category = _select_token(["category"], "'legacy'")
        select_action = _select_token(["action", "event_type"], "'unknown'")
        select_actor = _select_token(["actor"], "'system'")
        select_target = _select_token(["target", "correlation_id"], "'unknown'")
        select_metadata = _select_token(["metadata"], "'{}'")
        select_created_at = _select_token(
            ["created_at"], "'1970-01-01T00:00:00+00:00'"
        )

        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs_migrated (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    target TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                f"""
                INSERT INTO audit_logs_migrated (id, category, action, actor, target, metadata, created_at)
                SELECT
                    {select_id},
                    {select_category},
                    {select_action},
                    {select_actor},
                    {select_target},
                    {select_metadata},
                    {select_created_at}
                FROM audit_logs
                """
            )
            conn.execute("DROP TABLE audit_logs")
            conn.execute("ALTER TABLE audit_logs_migrated RENAME TO audit_logs")
        except Exception:
            logger.debug("Audit log migration failed", exc_info=True)

    def list_tables(self) -> List[str]:
        """テーブル一覧を返す（テスト用ヘルパー）。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            return [row["name"] for row in rows]

    # Credential operations
    def save_credential(self, record: CredentialRecord) -> None:
        """資格情報レコードを保存する。"""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO credentials (
                    credential_key, token_ref, scopes, expires_at,
                    server_id, oauth_token_url, oauth_client_id, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.credential_key,
                    json.dumps(record.token_ref),
                    json.dumps(record.scopes),
                    _to_iso(record.expires_at),
                    record.server_id,
                    record.oauth_token_url,
                    record.oauth_client_id,
                    record.created_by,
                    _to_iso(record.created_at),
                ),
            )
            conn.commit()

    def get_credential(self, credential_key: str) -> Optional[CredentialRecord]:
        """資格情報レコードを取得する。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM credentials WHERE credential_key=?",
                (credential_key,),
            ).fetchone()
        if row is None:
            return None
        return CredentialRecord(
            credential_key=row["credential_key"],
            token_ref=json.loads(row["token_ref"]),
            scopes=json.loads(row["scopes"]),
            expires_at=_from_iso(row["expires_at"]),
            server_id=row["server_id"],
            oauth_token_url=row["oauth_token_url"] if "oauth_token_url" in row.keys() else None,
            oauth_client_id=row["oauth_client_id"] if "oauth_client_id" in row.keys() else None,
            created_by=row["created_by"],
            created_at=_from_iso(row["created_at"]),
        )

    def list_credentials(self) -> List[CredentialRecord]:
        """資格情報レコードを全件取得する。"""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM credentials").fetchall()
        return [
            CredentialRecord(
                credential_key=row["credential_key"],
                token_ref=json.loads(row["token_ref"]),
                scopes=json.loads(row["scopes"]),
                expires_at=_from_iso(row["expires_at"]),
                server_id=row["server_id"],
                oauth_token_url=row["oauth_token_url"] if "oauth_token_url" in row.keys() else None,
                oauth_client_id=row["oauth_client_id"] if "oauth_client_id" in row.keys() else None,
                created_by=row["created_by"],
                created_at=_from_iso(row["created_at"]),
            )
            for row in rows
        ]

    def delete_credential(self, credential_key: str) -> None:
        """資格情報レコードを削除する。存在しない場合は何もしない。"""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM credentials WHERE credential_key=?",
                (credential_key,),
            )
            conn.commit()

    # Remote server operations
    def save_remote_server(self, record: RemoteServerRecord) -> None:
        """リモートサーバーレコードを保存する。"""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO remote_servers (
                    server_id, catalog_item_id, name, endpoint, status,
                    credential_key, last_connected_at, error_message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.server_id,
                    record.catalog_item_id,
                    record.name,
                    record.endpoint,
                    record.status,
                    record.credential_key,
                    _to_iso(record.last_connected_at) if record.last_connected_at else None,
                    record.error_message,
                    _to_iso(record.created_at),
                ),
            )
            conn.commit()

    def get_remote_server(self, server_id: str) -> Optional[RemoteServerRecord]:
        """リモートサーバーレコードを取得する。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM remote_servers WHERE server_id=?",
                (server_id,),
            ).fetchone()
        if row is None:
            return None
        return RemoteServerRecord(
            server_id=row["server_id"],
            catalog_item_id=row["catalog_item_id"],
            name=row["name"],
            endpoint=row["endpoint"],
            status=row["status"],
            credential_key=row["credential_key"],
            last_connected_at=_from_iso(row["last_connected_at"]) if row["last_connected_at"] else None,
            error_message=row["error_message"],
            created_at=_from_iso(row["created_at"]),
        )

    def list_remote_servers(self) -> List[RemoteServerRecord]:
        """リモートサーバーレコードを全件取得する。"""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM remote_servers").fetchall()
        records: List[RemoteServerRecord] = []
        for row in rows:
            records.append(
                RemoteServerRecord(
                    server_id=row["server_id"],
                    catalog_item_id=row["catalog_item_id"],
                    name=row["name"],
                    endpoint=row["endpoint"],
                    status=row["status"],
                    credential_key=row["credential_key"],
                    last_connected_at=_from_iso(row["last_connected_at"]) if row["last_connected_at"] else None,
                    error_message=row["error_message"],
                    created_at=_from_iso(row["created_at"]),
                )
            )
        return records

    def delete_remote_server(self, server_id: str) -> None:
        """リモートサーバーレコードを削除する。存在しない場合は何もしない。"""
        with self._connect() as conn:
            conn.execute("DELETE FROM remote_servers WHERE server_id=?", (server_id,))
            conn.commit()

    # OAuth state operations
    def save_oauth_state(self, record: OAuthStateRecord) -> None:
        """OAuth state レコードを保存する。"""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO oauth_states (
                    state, server_id, code_challenge, code_challenge_method, scopes,
                    authorize_url, token_url, client_id, redirect_uri, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.state,
                    record.server_id,
                    record.code_challenge,
                    record.code_challenge_method,
                    json.dumps(record.scopes),
                    record.authorize_url,
                    record.token_url,
                    record.client_id,
                    record.redirect_uri,
                    _to_iso(record.expires_at),
                    _to_iso(record.created_at),
                ),
            )
            conn.commit()

    def get_oauth_state(self, state: str) -> Optional[OAuthStateRecord]:
        """OAuth state レコードを取得する。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM oauth_states WHERE state=?",
                (state,),
            ).fetchone()

        if row is None:
            return None
        return OAuthStateRecord(
            state=row["state"],
            server_id=row["server_id"],
            code_challenge=row["code_challenge"],
            code_challenge_method=row["code_challenge_method"],
            scopes=json.loads(row["scopes"]),
            authorize_url=row["authorize_url"],
            token_url=row["token_url"],
            client_id=row["client_id"],
            redirect_uri=row["redirect_uri"],
            expires_at=_from_iso(row["expires_at"]),
            created_at=_from_iso(row["created_at"]),
        )

    def delete_oauth_state(self, state: str) -> None:
        """OAuth state レコードを削除する。存在しない場合は何もしない。"""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM oauth_states WHERE state=?",
                (state,),
            )
            conn.commit()

    # Container config operations
    def save_container_config(self, record: ContainerConfigRecord) -> None:
        """コンテナ設定レコードを保存する。"""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO container_configs (
                    container_id, name, image, config, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.container_id,
                    record.name,
                    record.image,
                    json.dumps(record.config),
                    _to_iso(record.created_at),
                ),
            )
            conn.commit()

    def get_container_config(self, container_id: str) -> Optional[ContainerConfigRecord]:
        """コンテナ設定レコードを取得する。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM container_configs WHERE container_id=?",
                (container_id,),
            ).fetchone()
        if row is None:
            return None
        return ContainerConfigRecord(
            container_id=row["container_id"],
            name=row["name"],
            image=row["image"],
            config=json.loads(row["config"]),
            created_at=_from_iso(row["created_at"]),
        )

    # GitHub token operations
    def save_github_token(self, record: GitHubTokenRecord) -> None:
        """GitHub トークンレコードを保存する（単一行）。"""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO github_tokens (id, token_ref, source, updated_by, updated_at)
                VALUES (1, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    token_ref=excluded.token_ref,
                    source=excluded.source,
                    updated_by=excluded.updated_by,
                    updated_at=excluded.updated_at
                """,
                (
                    json.dumps(record.token_ref),
                    record.source,
                    record.updated_by,
                    _to_iso(record.updated_at),
                ),
            )
            conn.commit()

    def get_github_token(self) -> Optional[GitHubTokenRecord]:
        """GitHub トークンレコードを取得する。存在しない場合は None。"""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM github_tokens WHERE id=1").fetchone()
        if row is None:
            return None
        return GitHubTokenRecord(
            token_ref=json.loads(row["token_ref"]),
            source=row["source"],
            updated_by=row["updated_by"],
            updated_at=_from_iso(row["updated_at"]),
        )

    def delete_github_token(self) -> None:
        """GitHub トークンレコードを削除する。存在しない場合は何もしない。"""
        with self._connect() as conn:
            conn.execute("DELETE FROM github_tokens WHERE id=1")
            conn.commit()

    # Auth session operations
    def save_auth_session(self, record: AuthSessionRecord) -> None:
        """ログインセッションレコードを保存する。"""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO auth_sessions (
                    session_id, user_email, bw_session_key,
                    created_at, expires_at, last_activity
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.session_id,
                    record.user_email,
                    record.bw_session_key,
                    _to_iso(record.created_at),
                    _to_iso(record.expires_at),
                    _to_iso(record.last_activity),
                ),
            )
            conn.commit()

    def get_auth_session(self, session_id: str) -> Optional[AuthSessionRecord]:
        """ログインセッションレコードを取得する。存在しない場合は None。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM auth_sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        return AuthSessionRecord(
            session_id=row["session_id"],
            user_email=row["user_email"],
            bw_session_key=row["bw_session_key"],
            created_at=_from_iso(row["created_at"]),
            expires_at=_from_iso(row["expires_at"]),
            last_activity=_from_iso(row["last_activity"]),
        )

    def list_auth_sessions(self) -> List[AuthSessionRecord]:
        """全ログインセッションレコードを取得する。"""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM auth_sessions").fetchall()
        sessions: List[AuthSessionRecord] = []
        for row in rows:
            sessions.append(
                AuthSessionRecord(
                    session_id=row["session_id"],
                    user_email=row["user_email"],
                    bw_session_key=row["bw_session_key"],
                    created_at=_from_iso(row["created_at"]),
                    expires_at=_from_iso(row["expires_at"]),
                    last_activity=_from_iso(row["last_activity"]),
                )
            )
        return sessions

    def delete_auth_session(self, session_id: str) -> None:
        """ログインセッションレコードを削除する。存在しない場合は何もしない。"""
        with self._connect() as conn:
            conn.execute("DELETE FROM auth_sessions WHERE session_id=?", (session_id,))
            conn.commit()

    # Session operations
    def save_session(self, record: SessionRecord) -> None:
        """セッションレコードを保存する。"""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions (
                    session_id, server_id, config, state, idle_deadline,
                    gateway_endpoint, metrics_endpoint, mtls_cert_ref,
                    feature_flags, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.session_id,
                    record.server_id,
                    json.dumps(record.config),
                    record.state,
                    _to_iso(record.idle_deadline),
                    record.gateway_endpoint,
                    record.metrics_endpoint,
                    json.dumps(record.mtls_cert_ref) if record.mtls_cert_ref else None,
                    json.dumps(record.feature_flags),
                    _to_iso(record.created_at),
                ),
            )
            conn.commit()

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """セッションレコードを取得する。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        return SessionRecord(
            session_id=row["session_id"],
            server_id=row["server_id"],
            config=json.loads(row["config"]),
            state=row["state"],
            idle_deadline=_from_iso(row["idle_deadline"]),
            gateway_endpoint=row["gateway_endpoint"],
            metrics_endpoint=row["metrics_endpoint"],
            mtls_cert_ref=json.loads(row["mtls_cert_ref"])
            if row["mtls_cert_ref"]
            else None,
            feature_flags=json.loads(row["feature_flags"]),
            created_at=_from_iso(row["created_at"]),
        )

    def delete_session(self, session_id: str) -> None:
        """セッションレコードを削除する。存在しない場合は何もしない。"""
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
            conn.commit()

    # Job operations
    def save_job(self, record: JobRecord) -> None:
        """ジョブレコードを保存する。"""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs (
                    job_id, session_id, status, queued_at, started_at,
                    finished_at, exit_code, timeout, truncated, output_ref, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_id,
                    record.session_id,
                    record.status,
                    _to_iso(record.queued_at),
                    _to_iso(record.started_at) if record.started_at else None,
                    _to_iso(record.finished_at) if record.finished_at else None,
                    record.exit_code,
                    int(record.timeout),
                    int(record.truncated),
                    json.dumps(record.output_ref) if record.output_ref else None,
                    _to_iso(record.created_at),
                ),
            )
            conn.commit()

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        """ジョブレコードを取得する。"""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            return None
        return JobRecord(
            job_id=row["job_id"],
            session_id=row["session_id"],
            status=row["status"],
            queued_at=_from_iso(row["queued_at"]),
            started_at=_from_iso(row["started_at"]) if row["started_at"] else None,
            finished_at=_from_iso(row["finished_at"]) if row["finished_at"] else None,
            exit_code=row["exit_code"],
            timeout=bool(row["timeout"]),
            truncated=bool(row["truncated"]),
            output_ref=json.loads(row["output_ref"]) if row["output_ref"] else None,
            created_at=_from_iso(row["created_at"]),
        )

    # Signature policy operations
    def save_signature_policy(self, record: SignaturePolicyRecord) -> None:
        """署名ポリシーを保存する。"""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO signature_policies (
                    server_id, payload, updated_at
                ) VALUES (?, ?, ?)
                """,
                (
                    record.server_id,
                    json.dumps(record.payload),
                    _to_iso(record.updated_at),
                ),
            )
            conn.commit()

    def get_signature_policy(self, server_id: str) -> Optional[SignaturePolicyRecord]:
        """署名ポリシーを取得する。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM signature_policies WHERE server_id=?", (server_id,)
            ).fetchone()
        if row is None:
            return None
        return SignaturePolicyRecord(
            server_id=row["server_id"],
            payload=json.loads(row["payload"]),
            updated_at=_from_iso(row["updated_at"]),
        )

    # Gateway allowlist operations
    def save_gateway_allow_entry(self, record: GatewayAllowEntry) -> None:
        """外部ゲートウェイ許可リストを保存する。"""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO gateway_allowlist (
                    id, type, value, created_by, created_at, enabled, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.type,
                    record.value,
                    record.created_by,
                    _to_iso(record.created_at),
                    int(record.enabled),
                    record.version,
                ),
            )
            conn.commit()

    def list_gateway_allow_entries(self) -> List[GatewayAllowEntry]:
        """許可リストを全件取得する。"""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM gateway_allowlist").fetchall()
        entries: List[GatewayAllowEntry] = []
        for row in rows:
            entries.append(
                GatewayAllowEntry(
                    id=row["id"],
                    type=row["type"],
                    value=row["value"],
                    created_by=row["created_by"],
                    created_at=_from_iso(row["created_at"]),
                    enabled=bool(row["enabled"]),
                    version=row["version"],
                )
            )
        return entries

    # Audit log operations
    def record_audit_log(
        self,
        category: str,
        action: str,
        actor: str,
        target: str,
        metadata: Dict[str, object],
        created_at: Optional[datetime] = None,
    ) -> None:
        """監査ログを保存する。"""
        sanitized = self._sanitize_metadata(metadata)
        timestamp = created_at or datetime.now(timezone.utc)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (category, action, actor, target, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    category,
                    action,
                    actor,
                    target,
                    json.dumps(sanitized),
                    _to_iso(timestamp),
                ),
            )
            conn.commit()

    def is_endpoint_allowed(self, url: str) -> bool:
        """
        REMOTE_MCP_ALLOWED_DOMAINS に基づきエンドポイント URL を検証する。

        空リストは deny-all とし、IPv6 リテラルはセキュリティ理由で拒否する。
        """
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            return False
        if ":" in host:
            return False

        scheme = (parsed.scheme or "").lower()
        port = parsed.port or (443 if scheme == "https" else 80)

        raw_allowlist = os.getenv("REMOTE_MCP_ALLOWED_DOMAINS", "")
        allowlist = [entry.strip().lower() for entry in raw_allowlist.split(",") if entry.strip()]
        if not allowlist:
            return False

        for entry in allowlist:
            entry_host = entry
            entry_port = None
            if ":" in entry:
                entry_host, entry_port_str = entry.rsplit(":", 1)
                try:
                    entry_port = int(entry_port_str)
                except ValueError:
                    continue
            else:
                entry_port = 443 if scheme == "https" else 80

            if entry_host.startswith("*."):
                suffix = entry_host[2:]
                if host.endswith("." + suffix) and entry_port == port:
                    return True
            elif host == entry_host and entry_port == port:
                return True

        return False

    def get_recent_audit_logs(self, limit: int = 20) -> List[AuditLogEntry]:
        """最近の監査ログを取得する。"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM audit_logs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result: List[AuditLogEntry] = []
        for row in rows:
            result.append(
                AuditLogEntry(
                    id=row["id"],
                    category=row["category"],
                    action=row["action"],
                    actor=row["actor"],
                    target=row["target"],
                    metadata=json.loads(row["metadata"]),
                    created_at=_from_iso(row["created_at"]),
                )
            )
        return result

    # GC
    def gc_expired(self, now: Optional[datetime] = None) -> Dict[str, int]:
        """
        期限切れデータを削除する。

        Returns:
            削除件数のディクショナリ。
        """
        now = now or datetime.now(timezone.utc)
        credential_cutoff = now - timedelta(days=settings.credential_retention_days)
        job_cutoff = now - timedelta(hours=settings.job_retention_hours)
        session_cutoff = now

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM credentials WHERE expires_at < ?",
                (_to_iso(credential_cutoff),),
            )
            cred_deleted = cur.rowcount

            cur.execute(
                "DELETE FROM sessions WHERE idle_deadline < ?",
                (_to_iso(session_cutoff),),
            )
            session_deleted = cur.rowcount

            cur.execute(
                """
                DELETE FROM jobs
                WHERE COALESCE(finished_at, queued_at) < ?
                """,
                (_to_iso(job_cutoff),),
            )
            job_deleted = cur.rowcount

            cur.execute(
                "DELETE FROM auth_sessions WHERE expires_at < ?",
                (_to_iso(now),),
            )
            auth_session_deleted = cur.rowcount

            cur.execute(
                "DELETE FROM oauth_states WHERE expires_at < ?",
                (_to_iso(now),),
            )
            oauth_state_deleted = cur.rowcount

            conn.commit()

        return {
            "credentials": cred_deleted,
            "sessions": session_deleted,
            "jobs": job_deleted,
            "auth_sessions": auth_session_deleted,
            "oauth_states": oauth_state_deleted,
        }

    def _sanitize_metadata(self, metadata: Dict[str, object]) -> Dict[str, object]:
        """秘密情報を含むキーをマスクする。"""
        sanitized: Dict[str, object] = {}
        for key, value in metadata.items():
            lowered = key.lower()
            if any(token in lowered for token in ["token", "credential", "secret"]):
                sanitized[key] = "***redacted***"
            else:
                sanitized[key] = value
        return sanitized
