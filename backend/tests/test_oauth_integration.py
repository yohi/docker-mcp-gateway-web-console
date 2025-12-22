"""OAuth フロー統合テスト。"""

import base64
import socket

import httpx
import pytest
from httpx import AsyncClient

from app.main import app
from app.services.oauth import OAuthService
from app.services.remote_mcp import RemoteMcpService
from app.services.state_store import StateStore


@pytest.fixture()
def setup_services(monkeypatch, tmp_path):
    """単一の StateStore を使うように API サービスを差し替える。"""
    from app.api import oauth as oauth_api
    from app.api import remote_mcp
    from app.config import settings

    # DNS をパブリック IP に解決させ、プライベート判定を避ける
    original_gethostbyname = socket.gethostbyname

    def mock_gethostbyname(hostname: str) -> str:  # noqa: ANN001
        if hostname in ("auth.example.com", "api.example.com"):
            return "93.184.216.34"
        return original_gethostbyname(hostname)

    monkeypatch.setattr(socket, "gethostbyname", mock_gethostbyname)

    # 設定をテスト用に固定
    monkeypatch.setattr(settings, "oauth_authorize_url", "https://auth.example.com/authorize")
    monkeypatch.setattr(settings, "oauth_token_url", "https://auth.example.com/token")
    monkeypatch.setattr(settings, "oauth_client_id", "client-123")
    monkeypatch.setattr(
        settings, "oauth_redirect_uri", "http://localhost:8000/api/catalog/oauth/callback"
    )
    key = base64.urlsafe_b64encode(b"0" * 32).decode()
    monkeypatch.setattr(settings, "oauth_token_encryption_key", key)
    monkeypatch.setattr(settings, "oauth_allowed_domains", "auth.example.com,api.example.com")
    monkeypatch.setenv("REMOTE_MCP_ALLOWED_DOMAINS", "api.example.com")

    db_path = tmp_path / "state.db"
    store = StateStore(str(db_path))
    store.init_schema()

    remote_service = RemoteMcpService(state_store=store)
    oauth_service = OAuthService(
        state_store=store, permitted_scopes=["repo:read"], credential_creator="test-admin"
    )

    monkeypatch.setattr(remote_mcp, "remote_service", remote_service)
    monkeypatch.setattr(oauth_api, "oauth_service", oauth_service)

    return {"remote_service": remote_service, "oauth_service": oauth_service}


@pytest.mark.asyncio
async def test_oauth_flow_register_to_callback(monkeypatch, setup_services):
    """登録→OAuth 開始→コールバックでトークン保存まで一連の成功を検証する。"""
    from app.api import oauth as oauth_api_module

    code_verifier = "integration-verifier-1234567890"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    class DummyTokenClient:
        def __init__(self, *args, **kwargs):
            return

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
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

    # OAuthService 内で使用する httpx.AsyncClient を差し替える
    monkeypatch.setattr("app.services.oauth.httpx.AsyncClient", DummyTokenClient)

    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        register_resp = await ac.post(
            "/api/remote-servers",
            json={
                "catalog_item_id": "cat-int",
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
    body = callback_resp.json()
    assert body["success"] is True
    assert body["credential_key"]

    credential = setup_services["oauth_service"].state_store.get_credential(body["credential_key"])
    assert credential is not None
    assert credential.server_id == server_id
    assert credential.scopes == ["repo:read"]
