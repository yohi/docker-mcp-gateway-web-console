import pytest
import httpx
from httpx import AsyncClient
from app.main import app


@pytest.fixture(autouse=True)
def configure_oauth_settings(monkeypatch):
    """OAuth設定をテスト用に固定化する。"""
    from app.config import settings

    monkeypatch.setattr(settings, "oauth_authorize_url", "https://auth.example.com/authorize")
    monkeypatch.setattr(settings, "oauth_token_url", "https://auth.example.com/token")
    monkeypatch.setattr(settings, "oauth_client_id", "client-123")
    monkeypatch.setattr(settings, "oauth_redirect_uri", "http://localhost:8000/api/catalog/oauth/callback")
    monkeypatch.setattr(settings, "oauth_request_timeout_seconds", 2)
    yield


@pytest.fixture()
def reset_oauth_service(monkeypatch):
    """テストごとに OAuth サービスの状態をリセットする。"""
    from app.api import oauth

    oauth.oauth_service = oauth.OAuthService()
    return oauth.oauth_service


@pytest.mark.asyncio
async def test_oauth_initiate_returns_state_and_pkce(reset_oauth_service):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/catalog/oauth/initiate",
            json={"server_id": "srv-1", "scopes": ["repo:read"]},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["state"]
    assert data["pkce_verifier"]
    assert data["required_scopes"] == ["repo:read"]
    assert data["auth_url"].startswith("https://auth.example.com/authorize")
    assert f"state={data['state']}" in data["auth_url"]
    assert "code_challenge=" in data["auth_url"]


@pytest.mark.asyncio
async def test_oauth_callback_state_mismatch_returns_401(reset_oauth_service):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(
            "/api/catalog/oauth/callback",
            params={"code": "abc", "state": "invalid", "server_id": "srv-1"},
        )

    assert response.status_code == 401
    assert "state" in response.json()["message"]


@pytest.mark.asyncio
async def test_oauth_callback_provider_4xx_returns_400(monkeypatch, reset_oauth_service):
    from app.services import oauth as oauth_service_module

    class DummyClient:
        call_count = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None, headers=None, timeout=None):
            DummyClient.call_count += 1
            return httpx.Response(
                status_code=400,
                request=httpx.Request("POST", url),
                json={"error": "invalid_grant"},
            )

    monkeypatch.setattr(oauth_service_module.httpx, "AsyncClient", DummyClient)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        init_resp = await ac.post(
            "/api/catalog/oauth/initiate",
            json={"server_id": "srv-1", "scopes": ["repo:read"]},
        )
        state = init_resp.json()["state"]

        response = await ac.get(
            "/api/catalog/oauth/callback",
            params={"code": "auth-code", "state": state, "server_id": "srv-1"},
        )

    assert response.status_code == 400
    assert "再認可" in response.json()["message"]
    assert DummyClient.call_count == 1


@pytest.mark.asyncio
async def test_oauth_callback_provider_5xx_retries_then_502(monkeypatch, reset_oauth_service):
    from app.services import oauth as oauth_service_module

    class FailingClient:
        call_count = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None, headers=None, timeout=None):
            FailingClient.call_count += 1
            return httpx.Response(
                status_code=500,
                request=httpx.Request("POST", url),
                json={"error": "server_error"},
            )

    async def immediate_sleep(seconds):
        return None

    monkeypatch.setattr(oauth_service_module.httpx, "AsyncClient", FailingClient)
    monkeypatch.setattr(oauth_service_module.asyncio, "sleep", immediate_sleep)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        init_resp = await ac.post(
            "/api/catalog/oauth/initiate",
            json={"server_id": "srv-1", "scopes": ["repo:read"]},
        )
        state = init_resp.json()["state"]

        response = await ac.get(
            "/api/catalog/oauth/callback",
            params={"code": "auth-code", "state": state, "server_id": "srv-1"},
        )

    assert response.status_code == 502
    assert "プロバイダ障害" in response.json()["message"]
    assert FailingClient.call_count == 3


@pytest.mark.asyncio
async def test_oauth_callback_success_returns_status(monkeypatch, reset_oauth_service):
    from app.services import oauth as oauth_service_module

    class SuccessClient:
        call_count = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None, headers=None, timeout=None):
            SuccessClient.call_count += 1
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

    monkeypatch.setattr(oauth_service_module.httpx, "AsyncClient", SuccessClient)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        init_resp = await ac.post(
            "/api/catalog/oauth/initiate",
            json={"server_id": "srv-1", "scopes": ["repo:read"]},
        )
        state = init_resp.json()["state"]

        response = await ac.get(
            "/api/catalog/oauth/callback",
            params={"code": "auth-code", "state": state, "server_id": "srv-1"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "authorized"
    assert SuccessClient.call_count == 1
