"""リモート MCP サーバー API の振る舞いを検証する。"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api import remote_mcp as remote_api
from app.main import app
from app.models.remote import RemoteServerStatus
from app.models.state import CredentialRecord
from app.services.remote_mcp import RemoteMcpService
from app.services.state_store import StateStore


client = TestClient(app)


class _DummySession:
    """SSE セッションのスタブ。"""

    def __init__(self, initialize_result: dict | None = None) -> None:
        self.initialize_called = 0
        self.ping_called = 0
        self._initialize_result = initialize_result or {"capabilities": []}

    async def initialize(self) -> dict:
        self.initialize_called += 1
        return self._initialize_result

    async def ping(self) -> None:
        self.ping_called += 1


class _DummyTransport:
    """SSE トランスポートのスタブ。"""

    def __init__(self, session: _DummySession) -> None:
        self._session = session

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
        return False

    async def connect(self):
        return self._session


def _make_transport_factory(session: _DummySession):
    """RemoteMcpService に渡す sse_client_factory を生成する。"""

    def _factory(endpoint: str, headers: dict | None = None, client=None):
        return _DummyTransport(session)

    return _factory


class _DummyHttpClient:
    """httpx.AsyncClient の代替として使う空のクライアント。"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
        return False


def _http_client_factory() -> _DummyHttpClient:
    return _DummyHttpClient()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def state_store(tmp_path) -> StateStore:
    """一時 SQLite ストアを用意する。"""

    db_path = tmp_path / "state.db"
    store = StateStore(str(db_path))
    store.init_schema()
    return store


@pytest.fixture
def remote_service(state_store, monkeypatch) -> RemoteMcpService:
    """API モジュールの RemoteMcpService をテスト用に差し替える。"""

    session = _DummySession()
    service = RemoteMcpService(
        state_store=state_store,
        sse_client_factory=_make_transport_factory(session),
        http_client_factory=_http_client_factory,
        max_connections=2,
    )
    monkeypatch.setattr(remote_api, "remote_service", service)
    return service


def _create_authenticated_server(service: RemoteMcpService, endpoint: str) -> str:
    server = _run(
        service.register_server(
            catalog_item_id="cat-1", name="Remote", endpoint=endpoint
        )
    )
    expires = datetime.now(timezone.utc) + timedelta(minutes=30)
    credential = CredentialRecord(
        credential_key="cred-1",
        token_ref={"type": "plaintext", "value": "token"},
        scopes=["sse"],
        expires_at=expires,
        server_id=server.server_id,
        oauth_token_url="https://auth.example.com/token",
        oauth_client_id="client-id",
        created_by="tester",
    )
    service.state_store.save_credential(credential)
    _run(
        service.set_status(
            server_id=server.server_id,
            status=RemoteServerStatus.AUTHENTICATED,
            credential_key=credential.credential_key,
        )
    )
    return server.server_id


def test_connect_endpoint_returns_capabilities(remote_service, monkeypatch) -> None:
    """POST /api/remote-servers/{id}/connect が capabilities を返す。"""

    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")
    server_id = _create_authenticated_server(
        remote_service, "https://api.example.com/sse"
    )

    response = client.post(f"/api/remote-servers/{server_id}/connect")

    assert response.status_code == 200
    body = response.json()
    assert body["server_id"] == server_id
    assert body["capabilities"] == {"capabilities": []}


def test_connect_endpoint_requires_credentials(remote_service, monkeypatch) -> None:
    """資格情報が無い場合は 401 を返す。"""

    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")
    server = _run(
        remote_service.register_server(
            catalog_item_id="cat-nocred",
            name="NoCred",
            endpoint="https://api.example.com/sse",
        )
    )

    response = client.post(f"/api/remote-servers/{server.server_id}/connect")

    assert response.status_code == 401
    body = response.json()
    assert body["error_code"] == "credential_missing"


def test_test_endpoint_reports_reachability(remote_service, monkeypatch) -> None:
    """POST /api/remote-servers/{id}/test が到達性と認証状態を返す。"""

    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")
    server_id = _create_authenticated_server(
        remote_service, "https://api.example.com/sse"
    )

    response = client.post(f"/api/remote-servers/{server_id}/test")

    assert response.status_code == 200
    data = response.json()
    assert data["server_id"] == server_id
    assert data["reachable"] is True
    assert data["authenticated"] is True
    assert data["capabilities"] == {"capabilities": []}


def test_test_endpoint_rejects_disallowed_endpoint(remote_service, monkeypatch) -> None:
    """許可リスト外のエンドポイントは 400 を返す。"""

    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "allowed.example.com")
    server_id = _create_authenticated_server(
        remote_service, "https://allowed.example.com/sse"
    )

    # テスト実行時に許可リストを空にして拒否させる
    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "")

    response = client.post(f"/api/remote-servers/{server_id}/test")

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "endpoint_not_allowed"


def test_register_remote_server_returns_record(remote_service, monkeypatch) -> None:
    """POST /api/remote-servers が登録済みサーバーを返す。"""
    _ = remote_service  # Fixture side effects required

    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")

    response = client.post(
        "/api/remote-servers",
        json={
            "catalog_item_id": "cat-1",
            "name": "Remote API",
            "endpoint": "https://api.example.com/sse",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["catalog_item_id"] == "cat-1"
    assert data["endpoint"] == "https://api.example.com/sse"
    assert RemoteServerStatus(data["status"]) == RemoteServerStatus.REGISTERED

    server_id = data["server_id"]
    get_response = client.get(f"/api/remote-servers/{server_id}")
    assert get_response.status_code == 200
    assert get_response.json()["server_id"] == server_id


def test_list_remote_servers_returns_all(remote_service, monkeypatch) -> None:
    """GET /api/remote-servers が登録済みの全サーバーを返す。"""

    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")
    first = _run(
        remote_service.register_server(
            catalog_item_id="cat-1",
            name="First",
            endpoint="https://api.example.com/sse",
        )
    )
    second = _run(
        remote_service.register_server(
            catalog_item_id="cat-2",
            name="Second",
            endpoint="https://api.example.com/sse2",
        )
    )

    response = client.get("/api/remote-servers")

    assert response.status_code == 200
    items = response.json()
    server_ids = {item["server_id"] for item in items}
    assert server_ids == {first.server_id, second.server_id}


def test_enable_and_disable_remote_server(remote_service, monkeypatch) -> None:
    """/enable と /disable がステータスを更新する。"""

    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")
    server = _run(
        remote_service.register_server(
            catalog_item_id="cat-3",
            name="EnableTest",
            endpoint="https://api.example.com/sse3",
        )
    )

    enable_resp = client.post(
        f"/api/remote-servers/{server.server_id}/enable", json={"requires_auth": True}
    )
    assert enable_resp.status_code == 200
    assert (
        RemoteServerStatus(enable_resp.json()["status"])
        == RemoteServerStatus.AUTH_REQUIRED
    )

    disable_resp = client.post(f"/api/remote-servers/{server.server_id}/disable")
    assert disable_resp.status_code == 200
    assert (
        RemoteServerStatus(disable_resp.json()["status"])
        == RemoteServerStatus.DISABLED
    )


def test_delete_remote_server_removes_record(remote_service, monkeypatch) -> None:
    """DELETE /api/remote-servers/{id} がレコードを削除する。"""

    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")
    server = _run(
        remote_service.register_server(
            catalog_item_id="cat-del",
            name="DeleteTest",
            endpoint="https://api.example.com/sse-del",
        )
    )

    delete_resp = client.delete(f"/api/remote-servers/{server.server_id}")
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/api/remote-servers/{server.server_id}")
    assert get_resp.status_code == 404
