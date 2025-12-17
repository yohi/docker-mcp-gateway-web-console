"""リモート MCP サーバー登録→認証→接続の統合テスト。"""

import asyncio
import base64

import httpx
import pytest
from httpx import AsyncClient

from app.api import oauth as oauth_api
from app.api import remote_mcp
from app.main import app
from app.models.remote import RemoteServerStatus
from app.services.oauth import OAuthService
from app.services.remote_mcp import RemoteMcpService, TooManyConnectionsError
from app.services.state_store import StateStore


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
    """RemoteMcpService 向け SSE トランスポートのスタブ。"""

    def __init__(self, session: _DummySession) -> None:
        self._session = session

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
        return False

    async def connect(self):
        return self._session


def _make_transport_factory(session: _DummySession):
    """sse_client_factory 用のファクトリ。"""

    def _factory(endpoint: str, headers: dict | None = None, client=None):
        return _DummyTransport(session)

    return _factory


class _DummyHttpClient:
    """httpx.AsyncClient の代替スタブ。"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
        return False


def _http_client_factory() -> _DummyHttpClient:
    return _DummyHttpClient()


@pytest.fixture()
def setup_services(monkeypatch, tmp_path):
    """単一の StateStore を共有する RemoteMcp/OAuth サービスを用意する。"""

    from app.config import settings

    # DNS をパブリック IP に解決させ、プライベート判定を避ける
    import socket

    original_gethostbyname = socket.gethostbyname

    def mock_gethostbyname(hostname: str) -> str:
        if hostname in ("auth.example.com", "api.example.com"):
            return "93.184.216.34"
        return original_gethostbyname(hostname)

    monkeypatch.setattr(socket, "gethostbyname", mock_gethostbyname)

    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")

    # OAuth 設定をテスト用に固定
    monkeypatch.setattr(settings, "oauth_authorize_url", "https://auth.example.com/authorize")
    monkeypatch.setattr(settings, "oauth_token_url", "https://auth.example.com/token")
    monkeypatch.setattr(settings, "oauth_client_id", "client-123")
    monkeypatch.setattr(
        settings, "oauth_redirect_uri", "http://localhost:8000/api/catalog/oauth/callback"
    )
    key = base64.urlsafe_b64encode(b"0" * 32).decode()
    monkeypatch.setattr(settings, "oauth_token_encryption_key", key)
    monkeypatch.setattr(settings, "oauth_allowed_domains", "auth.example.com,api.example.com")

    db_path = tmp_path / "state.db"
    store = StateStore(str(db_path))
    store.init_schema()

    session = _DummySession()
    remote_service = RemoteMcpService(
        state_store=store,
        sse_client_factory=_make_transport_factory(session),
        http_client_factory=_http_client_factory,
        max_connections=2,
    )
    oauth_service = OAuthService(
        state_store=store, permitted_scopes=["repo:read"], credential_creator="test-admin"
    )

    monkeypatch.setattr(remote_mcp, "remote_service", remote_service)
    monkeypatch.setattr(oauth_api, "oauth_service", oauth_service)

    return {"remote_service": remote_service, "oauth_service": oauth_service, "session": session}


class DummyTokenClient:
    """OAuth トークン交換で使用する httpx.AsyncClient のスタブ。"""

    def __init__(self, *args, **kwargs):
        return

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
        return False

    async def post(self, url, data=None, headers=None, timeout=None):
        return httpx.Response(
            status_code=200,
            request=httpx.Request("POST", url),
            json={
                "access_token": "token",
                "refresh_token": "refresh",
                "expires_in": 3600,
                "scope": "repo:read",
            },
        )


@pytest.fixture()
def load_test_services(monkeypatch, tmp_path):
    """負荷テスト用に接続上限とハートビート遅延を調整したサービスを提供する。"""

    from app.config import settings

    import socket

    original_gethostbyname = socket.gethostbyname

    def mock_gethostbyname(hostname: str) -> str:
        if hostname in ("auth.example.com", "api.example.com"):
            return "93.184.216.34"
        return original_gethostbyname(hostname)

    monkeypatch.setattr(socket, "gethostbyname", mock_gethostbyname)
    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")

    monkeypatch.setattr(settings, "oauth_authorize_url", "https://auth.example.com/authorize")
    monkeypatch.setattr(settings, "oauth_token_url", "https://auth.example.com/token")
    monkeypatch.setattr(settings, "oauth_client_id", "client-123")
    monkeypatch.setattr(
        settings, "oauth_redirect_uri", "http://localhost:8000/api/catalog/oauth/callback"
    )
    key = base64.urlsafe_b64encode(b"1" * 32).decode()
    monkeypatch.setattr(settings, "oauth_token_encryption_key", key)
    monkeypatch.setattr(settings, "oauth_allowed_domains", "auth.example.com,api.example.com")

    db_path = tmp_path / "state-perf.db"
    store = StateStore(str(db_path))
    store.init_schema()

    session = _DummySession()
    heartbeat_entered = asyncio.Event()

    async def _slow_heartbeat(*args):  # Accept session arg for _run_heartbeat compatibility
        heartbeat_entered.set()
        await asyncio.sleep(0.2)

    async def _fast_try_acquire():
        try:
            await asyncio.wait_for(remote_service._connection_semaphore.acquire(), timeout=0.05)  # type: ignore[attr-defined]
        except asyncio.TimeoutError as exc:
            raise TooManyConnectionsError("同時接続上限を超えています") from exc

    remote_service = RemoteMcpService(
        state_store=store,
        sse_client_factory=_make_transport_factory(session),
        http_client_factory=_http_client_factory,
        max_connections=1,
    )
    remote_service._run_heartbeat = _slow_heartbeat  # type: ignore[attr-defined]
    remote_service._try_acquire_connection_slot = _fast_try_acquire  # type: ignore[attr-defined]

    oauth_service = OAuthService(
        state_store=store, permitted_scopes=["repo:read"], credential_creator="test-admin"
    )

    monkeypatch.setattr(remote_mcp, "remote_service", remote_service)
    monkeypatch.setattr(oauth_api, "oauth_service", oauth_service)

    return {
        "remote_service": remote_service,
        "oauth_service": oauth_service,
        "session": session,
        "heartbeat_event": heartbeat_entered,
    }


@pytest.mark.asyncio
async def test_remote_server_register_auth_and_connect_flow(monkeypatch, setup_services):
    """登録→OAuth 認証→接続→接続テストの一連成功を検証する。"""

    code_verifier = "integration-verifier-connect-1234567890"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    # OAuthService 内で使用する httpx.AsyncClient をスタブに差し替える
    monkeypatch.setattr("app.services.oauth.httpx.AsyncClient", DummyTokenClient)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        register_resp = await ac.post(
            "/api/remote-servers",
            json={
                "catalog_item_id": "cat-integration",
                "name": "IntegrationServer",
                "endpoint": "https://api.example.com/sse",
            },
        )
        assert register_resp.status_code == 201
        server_id = register_resp.json()["server_id"]

        start_resp = await ac.post(
            "/api/oauth/start",
            json={
                "server_id": server_id,
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        assert start_resp.status_code == 200
        state = start_resp.json()["state"]

        callback_resp = await ac.get(
            "/api/oauth/callback",
            params={
                "code": "auth-code",
                "state": state,
                "server_id": server_id,
                "code_verifier": code_verifier,
            },
        )
        assert callback_resp.status_code == 200
        callback_body = callback_resp.json()
        assert callback_body["success"] is True
        credential_key = callback_body["credential_key"]

        credential = setup_services["oauth_service"].state_store.get_credential(credential_key)
        assert credential is not None
        assert credential.server_id == server_id
        assert credential.scopes == ["repo:read"]

        # OAuth 認可後にサーバーへ資格情報を紐づけて認証済み状態に更新
        await setup_services["remote_service"].set_status(
            server_id=server_id,
            status=RemoteServerStatus.AUTHENTICATED,
            credential_key=credential_key,
        )

        connect_resp = await ac.post(f"/api/remote-servers/{server_id}/connect")
        assert connect_resp.status_code == 200
        connect_body = connect_resp.json()
        assert connect_body["server_id"] == server_id
        assert connect_body["capabilities"] == {"capabilities": []}

        test_resp = await ac.post(f"/api/remote-servers/{server_id}/test")
        assert test_resp.status_code == 200
        test_body = test_resp.json()
        assert test_body["server_id"] == server_id
        assert test_body["reachable"] is True
        assert test_body["authenticated"] is True
        assert test_body["capabilities"] == {"capabilities": []}

        persisted = await setup_services["remote_service"].get_server(server_id)
        assert persisted is not None
        assert persisted.status == RemoteServerStatus.AUTHENTICATED
        assert persisted.last_connected_at is not None


@pytest.mark.asyncio
async def test_concurrent_oauth_flows_handle_10_parallel(monkeypatch, load_test_services):
    """10 並列の OAuth フローが衝突なく成功すること。"""

    monkeypatch.setattr("app.services.oauth.httpx.AsyncClient", DummyTokenClient)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        register_resp = await ac.post(
            "/api/remote-servers",
            json={
                "catalog_item_id": "cat-perf",
                "name": "PerfServer",
                "endpoint": "https://api.example.com/sse",
            },
        )
        assert register_resp.status_code == 201
        server_id = register_resp.json()["server_id"]

        async def _run_flow(idx: int) -> str:
            code_verifier = f"perf-verifier-{idx:02d}-1234567890"
            code_challenge = OAuthService._compute_code_challenge(code_verifier)
            start_resp = await ac.post(
                "/api/oauth/start",
                json={
                    "server_id": server_id,
                    "scopes": ["repo:read"],
                    "code_challenge": code_challenge,
                    "code_challenge_method": "S256",
                },
            )
            assert start_resp.status_code == 200
            state = start_resp.json()["state"]

            callback_resp = await ac.get(
                "/api/oauth/callback",
                params={
                    "code": f"auth-code-{idx}",
                    "state": state,
                    "server_id": server_id,
                    "code_verifier": code_verifier,
                },
            )
            assert callback_resp.status_code == 200
            body = callback_resp.json()
            assert body["success"] is True
            return body["credential_key"]

        credential_keys = await asyncio.gather(*(_run_flow(i) for i in range(10)))
        assert len(set(credential_keys)) == 10

        store = load_test_services["oauth_service"].state_store
        for key in credential_keys:
            record = store.get_credential(key)
            assert record is not None
            assert record.server_id == server_id
            assert record.scopes == ["repo:read"]


@pytest.mark.asyncio
async def test_connect_returns_429_when_connection_limit_exceeded(
    monkeypatch, load_test_services
):
    """接続上限超過時に 429 が返ること。"""

    heartbeat_event: asyncio.Event = load_test_services["heartbeat_event"]
    remote_service: RemoteMcpService = load_test_services["remote_service"]

    monkeypatch.setattr("app.services.oauth.httpx.AsyncClient", DummyTokenClient)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        register_resp = await ac.post(
            "/api/remote-servers",
            json={
                "catalog_item_id": "cat-max",
                "name": "MaxServer",
                "endpoint": "https://api.example.com/sse",
            },
        )
        assert register_resp.status_code == 201
        server_id = register_resp.json()["server_id"]

        code_verifier = "connect-limit-verifier-1234567890"
        code_challenge = OAuthService._compute_code_challenge(code_verifier)
        start_resp = await ac.post(
            "/api/oauth/start",
            json={
                "server_id": server_id,
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        state = start_resp.json()["state"]
        callback_resp = await ac.get(
            "/api/oauth/callback",
            params={
                "code": "auth-code-limit",
                "state": state,
                "server_id": server_id,
                "code_verifier": code_verifier,
            },
        )
        credential_key = callback_resp.json()["credential_key"]

        await remote_service.set_status(
            server_id=server_id,
            status=RemoteServerStatus.AUTHENTICATED,
            credential_key=credential_key,
        )

        first = asyncio.create_task(ac.post(f"/api/remote-servers/{server_id}/connect"))
        await heartbeat_event.wait()
        second = await ac.post(f"/api/remote-servers/{server_id}/connect")
        first_resp = await first

        assert first_resp.status_code == 200
        assert second.status_code == 429
