"""永続化ストアのTDDテスト。"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models.state import (
    AuthSessionRecord,
    CredentialRecord,
    GatewayAllowEntry,
    JobRecord,
    SessionRecord,
    SignaturePolicyRecord,
)
from app.services.state_store import StateStore


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    """一時ディレクトリに SQLite ストアを作成する。"""
    db_path = tmp_path / "state.db"
    state_store = StateStore(str(db_path))
    state_store.init_schema()
    return state_store


def test_schema_created(store: StateStore) -> None:
    """初期化で必要なテーブルが作成されることを検証する。"""
    tables = store.list_tables()
    expected = {
        "credentials",
        "sessions",
        "jobs",
        "signature_policies",
        "gateway_allowlist",
        "audit_logs",
        "github_tokens",
        "auth_sessions",
    }
    assert expected.issubset(tables)


def test_credential_gc(store: StateStore) -> None:
    """期限切れクレデンシャルが 30 日後に GC されることを検証する。"""
    now = datetime.now(timezone.utc)
    expired = CredentialRecord(
        credential_key="old",
        token_ref={"type": "encrypted", "key": "k1"},
        scopes=["scope:a"],
        expires_at=now - timedelta(days=31),
        server_id="srv",
        created_by="admin",
        created_at=now - timedelta(days=40),
    )
    valid = CredentialRecord(
        credential_key="new",
        token_ref={"type": "encrypted", "key": "k2"},
        scopes=["scope:a", "scope:b"],
        expires_at=now + timedelta(days=1),
        server_id="srv",
        created_by="admin",
        created_at=now,
    )
    store.save_credential(expired)
    store.save_credential(valid)

    removed = store.gc_expired(now=now)

    assert removed["credentials"] == 1
    assert store.get_credential("old") is None
    fetched = store.get_credential("new")
    assert fetched is not None
    assert fetched.scopes == ["scope:a", "scope:b"]


def test_session_gc_by_idle_deadline(store: StateStore) -> None:
    """アイドル期限切れのセッションのみ GC されることを検証する。"""
    now = datetime.now(timezone.utc)
    expired = SessionRecord(
        session_id="s-expired",
        server_id="srv",
        config={"cpuQuota": 512},
        state="running",
        idle_deadline=now - timedelta(minutes=1),
        gateway_endpoint="unix:///tmp/gw.sock",
        metrics_endpoint="http://localhost:9000/metrics",
        mtls_cert_ref={"type": "ephemeral", "handle": "h1"},
        feature_flags={"audit_only_signature": True},
        created_at=now - timedelta(minutes=10),
    )
    active = SessionRecord(
        session_id="s-active",
        server_id="srv",
        config={"cpuQuota": 512},
        state="running",
        idle_deadline=now + timedelta(minutes=20),
        gateway_endpoint="unix:///tmp/gw2.sock",
        metrics_endpoint="http://localhost:9001/metrics",
        mtls_cert_ref={"type": "ephemeral", "handle": "h2"},
        feature_flags={"audit_only_signature": True},
        created_at=now - timedelta(minutes=5),
    )
    store.save_session(expired)
    store.save_session(active)

    removed = store.gc_expired(now=now)

    assert removed["sessions"] == 1
    assert store.get_session("s-expired") is None
    assert store.get_session("s-active") is not None


def test_auth_session_gc_by_expires_at(store: StateStore) -> None:
    """期限切れの認証セッションが GC されることを検証する。"""
    now = datetime.now(timezone.utc)
    expired = AuthSessionRecord(
        session_id="auth-expired",
        user_email="user@example.com",
        bw_session_key="k1",
        created_at=now - timedelta(minutes=10),
        expires_at=now - timedelta(minutes=1),
        last_activity=now - timedelta(minutes=5),
    )
    active = AuthSessionRecord(
        session_id="auth-active",
        user_email="user@example.com",
        bw_session_key="k2",
        created_at=now,
        expires_at=now + timedelta(minutes=30),
        last_activity=now,
    )
    store.save_auth_session(expired)
    store.save_auth_session(active)

    removed = store.gc_expired(now=now)

    assert removed["auth_sessions"] == 1
    assert store.get_auth_session("auth-expired") is None
    assert store.get_auth_session("auth-active") is not None


def test_auth_session_roundtrip(store: StateStore) -> None:
    """ログインセッションが保存・取得・削除できることを検証する。"""
    now = datetime.now(timezone.utc)
    record = AuthSessionRecord(
        session_id="auth-1",
        user_email="user@example.com",
        bw_session_key="bw-session",
        created_at=now,
        expires_at=now + timedelta(minutes=30),
        last_activity=now,
    )

    store.save_auth_session(record)

    fetched = store.get_auth_session("auth-1")
    assert fetched is not None
    assert fetched.user_email == "user@example.com"
    assert fetched.bw_session_key == "bw-session"

    all_sessions = store.list_auth_sessions()
    assert len(all_sessions) == 1

    store.delete_auth_session("auth-1")
    assert store.get_auth_session("auth-1") is None


def test_job_gc_after_24_hours(store: StateStore) -> None:
    """ジョブが 24 時間後に GC されることを検証する。"""
    now = datetime.now(timezone.utc)
    old_job = JobRecord(
        job_id="job-old",
        session_id="s1",
        status="completed",
        queued_at=now - timedelta(hours=30),
        started_at=now - timedelta(hours=25),
        finished_at=now - timedelta(hours=24, minutes=30),
        exit_code=0,
        timeout=False,
        truncated=False,
        output_ref={"storage": "file", "path": "/tmp/out.txt"},
        created_at=now - timedelta(hours=30),
    )
    fresh_job = JobRecord(
        job_id="job-new",
        session_id="s1",
        status="running",
        queued_at=now - timedelta(hours=1),
        started_at=now - timedelta(minutes=10),
        finished_at=None,
        exit_code=None,
        timeout=False,
        truncated=False,
        output_ref=None,
        created_at=now - timedelta(hours=1),
    )
    store.save_job(old_job)
    store.save_job(fresh_job)

    removed = store.gc_expired(now=now)

    assert removed["jobs"] == 1
    assert store.get_job("job-old") is None
    assert store.get_job("job-new") is not None


def test_signature_policy_roundtrip(store: StateStore) -> None:
    """署名ポリシーが保存・取得できることを検証する。"""
    now = datetime.now(timezone.utc)
    policy = SignaturePolicyRecord(
        server_id="srv",
        payload={
            "mode": "audit-only",
            "verify_signatures": True,
            "allowed_algorithms": ["RSA-PSS-SHA256", "ECDSA-SHA256"],
        },
        updated_at=now,
    )
    store.save_signature_policy(policy)

    fetched = store.get_signature_policy("srv")

    assert fetched is not None
    assert fetched.payload["mode"] == "audit-only"
    assert fetched.payload["verify_signatures"] is True


def test_gateway_allowlist_roundtrip(store: StateStore) -> None:
    """許可リストが保存・取得できることを検証する。"""
    now = datetime.now(timezone.utc)
    entry = GatewayAllowEntry(
        id="gw1",
        type="domain",
        value="example.com",
        created_by="admin",
        created_at=now,
        enabled=True,
        version=1,
    )
    store.save_gateway_allow_entry(entry)
    entries = store.list_gateway_allow_entries()

    assert len(entries) == 1
    assert entries[0].value == "example.com"


def test_audit_log_sanitizes_tokens(store: StateStore) -> None:
    """監査ログにトークン値が残らないようにマスクされることを検証する。"""
    now = datetime.now(timezone.utc)
    store.record_audit_log(
        event_type="token_saved",
        correlation_id="corr-1",
        metadata={
            "token": "secret",
            "refresh_token": "refresh",
            "credential_key": "abc",
            "message": "ok",
        },
        created_at=now,
    )
    logs = store.get_recent_audit_logs(limit=5)

    assert logs
    metadata = logs[0].metadata
    assert metadata["token"] == "***redacted***"
    assert metadata["refresh_token"] == "***redacted***"
    assert metadata["credential_key"] == "***redacted***"
    assert metadata["message"] == "ok"
