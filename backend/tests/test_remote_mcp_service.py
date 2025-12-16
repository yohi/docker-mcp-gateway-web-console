"""RemoteMcpService の基盤機能テスト。"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.models.remote import RemoteServer, RemoteServerStatus
from app.models.state import CredentialRecord
from app.services.oauth import CredentialNotFoundError, RemoteServerNotFoundError
from app.services.remote_mcp import (
    DuplicateRemoteServerError,
    EndpointNotAllowedError,
    RemoteMcpService,
    TooManyConnectionsError,
)
from app.services.state_store import StateStore


class _DummySession:
    """テスト用 SSE セッションのスタブ。"""

    def __init__(self, initialize_result: dict | None = None, ping_delay: float = 0) -> None:
        self.initialize_called = 0
        self.ping_called = 0
        self._initialize_result = initialize_result or {"capabilities": []}
        self._ping_delay = ping_delay

    async def initialize(self) -> dict:
        self.initialize_called += 1
        return self._initialize_result

    async def ping(self) -> None:
        self.ping_called += 1
        if self._ping_delay:
            await asyncio.sleep(self._ping_delay)


class _DummyTransport:
    """テスト用 SSE トランスポートのスタブ。"""

    def __init__(self, session: _DummySession, on_connect=None) -> None:
        self._session = session
        self._on_connect = on_connect

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def connect(self):
        if self._on_connect:
            await self._on_connect()
        return self._session


def _make_transport_factory(session: _DummySession, on_connect=None):
    """sse_client_factory 用の簡易ファクトリ。"""

    def _factory(endpoint: str, headers: dict | None = None, client=None):
        return _DummyTransport(session, on_connect=on_connect)

    return _factory


def _make_service(tmp_path, **kwargs) -> RemoteMcpService:
    """テスト用の RemoteMcpService を作成する。"""
    db_path = tmp_path / "state.db"
    store = StateStore(str(db_path))
    store.init_schema()
    return RemoteMcpService(state_store=store, **kwargs)


@pytest.mark.asyncio
async def test_save_and_get_remote_server(tmp_path) -> None:
    """保存したリモートサーバーが取得できること。"""
    service = _make_service(tmp_path)
    now = datetime.now(timezone.utc)
    server = RemoteServer(
        server_id="srv-1",
        catalog_item_id="catalog-1",
        name="Sample",
        endpoint="https://api.example.com/sse",
        status=RemoteServerStatus.REGISTERED,
        created_at=now,
    )

    await service.save_server(server)

    fetched = await service.get_server("srv-1")
    assert fetched is not None
    assert fetched.server_id == server.server_id
    assert fetched.status == RemoteServerStatus.REGISTERED
    assert fetched.created_at == now


@pytest.mark.asyncio
async def test_list_servers_returns_all(tmp_path) -> None:
    """複数サーバーが一覧取得できること。"""
    service = _make_service(tmp_path)
    server_a = RemoteServer(
        server_id="srv-a",
        catalog_item_id="catalog-a",
        name="Alpha",
        endpoint="https://a.example.com/sse",
        status=RemoteServerStatus.REGISTERED,
    )
    server_b = RemoteServer(
        server_id="srv-b",
        catalog_item_id="catalog-b",
        name="Beta",
        endpoint="https://b.example.com/sse",
        status=RemoteServerStatus.AUTH_REQUIRED,
    )

    await service.save_server(server_a)
    await service.save_server(server_b)

    servers = await service.list_servers()
    ids = {item.server_id for item in servers}
    assert ids == {"srv-a", "srv-b"}


@pytest.mark.asyncio
async def test_set_status_updates_record(tmp_path) -> None:
    """ステータス更新が永続化されること。"""
    service = _make_service(tmp_path)
    server = RemoteServer(
        server_id="srv-status",
        catalog_item_id="catalog-status",
        name="Gamma",
        endpoint="https://gamma.example.com/sse",
        status=RemoteServerStatus.REGISTERED,
    )
    await service.save_server(server)

    updated = await service.set_status(
        server_id="srv-status",
        status=RemoteServerStatus.AUTHENTICATED,
        credential_key="cred-1",
        error_message="",
    )

    assert updated.status == RemoteServerStatus.AUTHENTICATED
    assert updated.credential_key == "cred-1"

    persisted = await service.get_server("srv-status")
    assert persisted is not None
    assert persisted.status == RemoteServerStatus.AUTHENTICATED
    assert persisted.credential_key == "cred-1"
    assert persisted.error_message == ""


@pytest.mark.asyncio
async def test_get_server_credential_validates_binding(tmp_path) -> None:
    """credential_key が server_id と正しく紐づいている場合に取得できる。"""
    service = _make_service(tmp_path)
    server = RemoteServer(
        server_id="srv-cred",
        catalog_item_id="catalog-cred",
        name="Delta",
        endpoint="https://delta.example.com/sse",
        status=RemoteServerStatus.AUTH_REQUIRED,
    )
    await service.save_server(server)

    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    record = CredentialRecord(
        credential_key="cred-xyz",
        token_ref={"type": "plaintext", "value": "abc"},
        scopes=["scope1"],
        expires_at=expires,
        server_id="srv-cred",
        oauth_token_url="https://auth.example.com/token",
        oauth_client_id="client-id",
        created_by="tester",
    )
    service.state_store.save_credential(record)
    await service.set_status(
        server_id="srv-cred",
        status=RemoteServerStatus.AUTHENTICATED,
        credential_key="cred-xyz",
    )

    credential = await service.get_server_credential("srv-cred")

    assert credential.credential_key == "cred-xyz"
    assert credential.server_id == "srv-cred"


@pytest.mark.asyncio
async def test_get_server_credential_raises_when_missing(tmp_path) -> None:
    """credential_key が存在しない場合に例外を送出する。"""
    service = _make_service(tmp_path)
    server = RemoteServer(
        server_id="srv-missing",
        catalog_item_id="catalog-missing",
        name="Epsilon",
        endpoint="https://epsilon.example.com/sse",
        status=RemoteServerStatus.REGISTERED,
    )
    await service.save_server(server)

    with pytest.raises(CredentialNotFoundError):
        await service.get_server_credential("srv-missing")


@pytest.mark.asyncio
async def test_set_status_raises_for_unknown_server(tmp_path) -> None:
    """存在しない server_id への更新は例外となる。"""
    service = _make_service(tmp_path)

    with pytest.raises(RemoteServerNotFoundError):
        await service.set_status("unknown", RemoteServerStatus.REGISTERED)


@pytest.mark.asyncio
async def test_register_server_saves_and_records_audit(tmp_path, monkeypatch) -> None:
    """許可されたエンドポイントを登録し、監査ログが残ること。"""
    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")
    service = _make_service(tmp_path)

    server = await service.register_server(
        catalog_item_id="cat-1",
        name="Example",
        endpoint="https://api.example.com/sse",
        correlation_id="corr-1",
    )

    persisted = await service.get_server(server.server_id)
    assert persisted is not None
    assert persisted.catalog_item_id == "cat-1"
    assert persisted.endpoint == "https://api.example.com/sse"

    logs = service.state_store.get_recent_audit_logs()
    assert any(
        log.event_type == "server_registered"
        and log.metadata.get("server_id") == server.server_id
        and log.metadata.get("endpoint") == "https://api.example.com/sse"
        for log in logs
    )


@pytest.mark.asyncio
async def test_register_server_rejects_not_allowed_endpoint(tmp_path, monkeypatch) -> None:
    """許可リストにないエンドポイントは登録できないこと。"""
    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "allowed.example.com")
    service = _make_service(tmp_path)

    with pytest.raises(EndpointNotAllowedError):
        await service.register_server(
            catalog_item_id="cat-2",
            name="NotAllowed",
            endpoint="https://blocked.example.com/sse",
            correlation_id="corr-2",
        )

    servers = await service.list_servers()
    assert servers == []

    logs = service.state_store.get_recent_audit_logs()
    assert any(log.event_type == "endpoint_rejected" for log in logs)


@pytest.mark.asyncio
async def test_register_server_rejects_duplicate(tmp_path, monkeypatch) -> None:
    """catalog_item_id または endpoint が重複する場合は拒否されること。"""
    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "dup.example.com")
    service = _make_service(tmp_path)

    await service.register_server(
        catalog_item_id="cat-dup",
        name="Dup",
        endpoint="https://dup.example.com/sse",
    )

    with pytest.raises(DuplicateRemoteServerError):
        await service.register_server(
            catalog_item_id="cat-dup",
            name="Dup2",
            endpoint="https://dup.example.com/sse",
        )

    servers = await service.list_servers()
    assert len(servers) == 1


@pytest.mark.asyncio
async def test_enable_server_sets_auth_required_and_records_audit(tmp_path, monkeypatch) -> None:
    """有効化時に認証が未設定なら auth_required に遷移し監査される。"""
    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")
    service = _make_service(tmp_path)

    server = await service.register_server(
        catalog_item_id="cat-enable",
        name="EnableMe",
        endpoint="https://api.example.com/sse",
    )

    updated = await service.enable_server(server.server_id, correlation_id="corr-enable")

    assert updated.status == RemoteServerStatus.AUTH_REQUIRED
    persisted = await service.get_server(server.server_id)
    assert persisted is not None
    assert persisted.status == RemoteServerStatus.AUTH_REQUIRED

    logs = service.state_store.get_recent_audit_logs()
    assert any(
        log.event_type == "server_enabled"
        and log.metadata.get("server_id") == server.server_id
        and log.metadata.get("to_status") == RemoteServerStatus.AUTH_REQUIRED.value
        for log in logs
    )


@pytest.mark.asyncio
async def test_enable_server_uses_credentials_when_present(tmp_path, monkeypatch) -> None:
    """credential がある場合は authenticated に遷移し監査される。"""
    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")
    service = _make_service(tmp_path)

    server = await service.register_server(
        catalog_item_id="cat-enable-cred",
        name="EnableWithCred",
        endpoint="https://api.example.com/sse",
    )

    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    credential = CredentialRecord(
        credential_key="cred-enable",
        token_ref={"type": "plaintext", "value": "secret"},
        scopes=["scope"],
        expires_at=expires,
        server_id=server.server_id,
        oauth_token_url="https://auth.example.com/token",
        oauth_client_id="client-id",
        created_by="tester",
    )
    service.state_store.save_credential(credential)
    await service.set_status(
        server_id=server.server_id,
        status=RemoteServerStatus.REGISTERED,
        credential_key=credential.credential_key,
    )

    updated = await service.enable_server(server.server_id)

    assert updated.status == RemoteServerStatus.AUTHENTICATED
    persisted = await service.get_server(server.server_id)
    assert persisted is not None
    assert persisted.status == RemoteServerStatus.AUTHENTICATED

    logs = service.state_store.get_recent_audit_logs()
    assert any(
        log.event_type == "server_enabled"
        and log.metadata.get("server_id") == server.server_id
        and log.metadata.get("to_status") == RemoteServerStatus.AUTHENTICATED.value
        for log in logs
    )


@pytest.mark.asyncio
async def test_disable_server_sets_disabled_and_records_audit(tmp_path, monkeypatch) -> None:
    """無効化時に disabled へ遷移し監査される。"""
    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")
    service = _make_service(tmp_path)

    server = await service.register_server(
        catalog_item_id="cat-disable",
        name="DisableMe",
        endpoint="https://api.example.com/sse",
    )

    updated = await service.disable_server(server.server_id, correlation_id="corr-disable")

    assert updated.status == RemoteServerStatus.DISABLED
    persisted = await service.get_server(server.server_id)
    assert persisted is not None
    assert persisted.status == RemoteServerStatus.DISABLED

    logs = service.state_store.get_recent_audit_logs()
    assert any(
        log.event_type == "server_disabled"
        and log.metadata.get("server_id") == server.server_id
        and log.metadata.get("to_status") == RemoteServerStatus.DISABLED.value
        for log in logs
    )


@pytest.mark.asyncio
async def test_delete_server_removes_credentials_when_requested(tmp_path, monkeypatch) -> None:
    """delete_credentials=True で紐づく資格情報も削除されること。"""
    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")
    service = _make_service(tmp_path)

    server = await service.register_server(
        catalog_item_id="cat-del",
        name="DeleteMe",
        endpoint="https://api.example.com/sse",
    )

    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    cred = CredentialRecord(
        credential_key="cred-del",
        token_ref={"type": "plaintext", "value": "secret"},
        scopes=["scope"],
        expires_at=expires,
        server_id=server.server_id,
        oauth_token_url="https://auth.example.com/token",
        oauth_client_id="client-id",
        created_by="tester",
    )
    service.state_store.save_credential(cred)
    await service.set_status(
        server_id=server.server_id,
        status=RemoteServerStatus.AUTHENTICATED,
        credential_key="cred-del",
    )

    await service.delete_server(
        server_id=server.server_id, delete_credentials=True, correlation_id="corr-del"
    )

    assert await service.get_server(server.server_id) is None
    assert service.state_store.get_credential("cred-del") is None

    logs = service.state_store.get_recent_audit_logs()
    assert any(log.event_type == "server_deleted" for log in logs)


@pytest.mark.asyncio
async def test_revoke_credentials_clears_token_and_sets_auth_required(tmp_path, monkeypatch) -> None:
    """認証解除で資格情報が削除され status=AUTH_REQUIRED になること。"""
    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")
    service = _make_service(tmp_path)

    server = await service.register_server(
        catalog_item_id="cat-revoke",
        name="RevokeMe",
        endpoint="https://api.example.com/sse",
    )

    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    cred = CredentialRecord(
        credential_key="cred-revoke",
        token_ref={"type": "plaintext", "value": "secret"},
        scopes=["scope"],
        expires_at=expires,
        server_id=server.server_id,
        oauth_token_url="https://auth.example.com/token",
        oauth_client_id="client-id",
        created_by="tester",
    )
    service.state_store.save_credential(cred)
    await service.set_status(
        server_id=server.server_id,
        status=RemoteServerStatus.AUTHENTICATED,
        credential_key=cred.credential_key,
    )

    updated = await service.revoke_credentials(
        server_id=server.server_id, correlation_id="corr-revoke"
    )

    assert updated.status == RemoteServerStatus.AUTH_REQUIRED
    assert updated.credential_key is None
    assert service.state_store.get_credential("cred-revoke") is None

    logs = service.state_store.get_recent_audit_logs()
    assert any(
        log.event_type == "credentials_revoked"
        and log.metadata.get("server_id") == server.server_id
        for log in logs
    )


@pytest.mark.asyncio
async def test_connect_uses_semaphore_and_rejects_when_busy(tmp_path, monkeypatch) -> None:
    """同時接続上限を超えると TooManyConnectionsError を返す。"""
    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")
    service = _make_service(tmp_path, max_connections=1)

    server = await service.register_server(
        catalog_item_id="cat-conc",
        name="Conc",
        endpoint="https://api.example.com/sse",
    )
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    cred = CredentialRecord(
        credential_key="cred-conc",
        token_ref={"type": "plaintext", "value": "token"},
        scopes=["sse"],
        expires_at=expires,
        server_id=server.server_id,
        oauth_token_url="https://auth.example.com/token",
        oauth_client_id="client",
        created_by="tester",
    )
    service.state_store.save_credential(cred)
    await service.set_status(
        server_id=server.server_id,
        status=RemoteServerStatus.AUTHENTICATED,
        credential_key=cred.credential_key,
    )

    first_session = _DummySession()
    start_event = asyncio.Event()
    release_event = asyncio.Event()

    async def _on_connect():
        start_event.set()
        await release_event.wait()

    factory = _make_transport_factory(first_session, on_connect=_on_connect)
    service._sse_client_factory = factory  # テスト用に差し替え

    # 1つ目の接続でセマフォを占有
    first_task = asyncio.create_task(service.connect(server.server_id))
    await start_event.wait()

    # 2つ目は TooManyConnectionsError
    with pytest.raises(TooManyConnectionsError):
        await service.connect(server.server_id)

    # 解放して完了
    release_event.set()
    result = await first_task
    assert result["capabilities"] == []


@pytest.mark.asyncio
async def test_connect_rejects_when_endpoint_not_allowed(tmp_path, monkeypatch) -> None:
    """接続時も許可リスト検証が行われる。"""
    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")
    service = _make_service(tmp_path)

    server = await service.register_server(
        catalog_item_id="cat-allow",
        name="Allow",
        endpoint="https://api.example.com/sse",
    )
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    cred = CredentialRecord(
        credential_key="cred-allow",
        token_ref={"type": "plaintext", "value": "token"},
        scopes=["sse"],
        expires_at=expires,
        server_id=server.server_id,
        oauth_token_url="https://auth.example.com/token",
        oauth_client_id="client",
        created_by="tester",
    )
    service.state_store.save_credential(cred)
    await service.set_status(
        server_id=server.server_id,
        status=RemoteServerStatus.AUTHENTICATED,
        credential_key=cred.credential_key,
    )

    # 接続時に allowlist を空にして拒否させる
    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "")
    service._sse_client_factory = _make_transport_factory(_DummySession())

    with pytest.raises(EndpointNotAllowedError):
        await service.connect(server.server_id)
