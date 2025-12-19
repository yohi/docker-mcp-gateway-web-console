import httpx
from httpx import AsyncClient
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pytest
from app.services.oauth import OAuthService, ScopeUpdateForbiddenError
from app.services.state_store import StateStore
from app.models.state import CredentialRecord, OAuthStateRecord, RemoteServerRecord
from app.main import app


@pytest.fixture(autouse=True)
def configure_oauth_settings(monkeypatch):
    """OAuth設定をテスト用に固定化する。"""
    from app.config import settings
    import base64
    import socket

    monkeypatch.setattr(settings, "oauth_authorize_url", "https://auth.example.com/authorize")
    monkeypatch.setattr(settings, "oauth_token_url", "https://auth.example.com/token")
    monkeypatch.setattr(settings, "oauth_client_id", "client-123")
    monkeypatch.setattr(settings, "oauth_redirect_uri", "http://localhost:8000/api/catalog/oauth/callback")
    monkeypatch.setattr(settings, "oauth_request_timeout_seconds", 2)
    monkeypatch.setattr(settings, "oauth_allowed_domains", "auth.example.com,api.example.com,github.com")
    key = base64.urlsafe_b64encode(b"0" * 32).decode()
    monkeypatch.setattr(settings, "oauth_token_encryption_key", key)
    monkeypatch.setattr(settings, "oauth_token_encryption_key_id", "test-key")

    # DNS解決のモック: テスト用ドメインをパブリックIPに解決
    original_gethostbyname = socket.gethostbyname

    def mock_gethostbyname(hostname):
        # テスト用ドメインは正常なパブリックIPに解決
        if hostname in ("auth.example.com", "api.example.com"):
            return "93.184.216.34"  # example.com の実際のIP
        return original_gethostbyname(hostname)

    monkeypatch.setattr(socket, "gethostbyname", mock_gethostbyname)
    yield


@pytest.fixture()
def reset_oauth_service(monkeypatch, tmp_path: Path):
    """テストごとに OAuth サービスの状態をリセットする。"""
    from app.api import oauth

    db_path = tmp_path / "state.db"
    store = StateStore(str(db_path))
    store.init_schema()
    store.save_remote_server(
        RemoteServerRecord(
            server_id="srv-1",
            catalog_item_id="cat-1",
            name="Remote Server 1",
            endpoint="https://api.example.com/sse",
            status="registered",
        )
    )
    oauth.oauth_service = oauth.OAuthService(
        state_store=store,
        permitted_scopes=["repo:read"],
        credential_creator="test-admin",
    )
    return oauth.oauth_service


@pytest.mark.asyncio
async def test_oauth_initiate_returns_state_and_auth_url(reset_oauth_service):
    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/catalog/oauth/initiate",
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["state"]
    assert "pkce_verifier" not in data
    assert data["required_scopes"] == ["repo:read"]
    assert data["auth_url"].startswith("https://auth.example.com/authorize")
    assert f"state={data['state']}" in data["auth_url"]
    assert f"code_challenge={code_challenge}" in data["auth_url"]


@pytest.mark.asyncio
async def test_oauth_initiate_persists_state(reset_oauth_service):
    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)
    store = reset_oauth_service.state_store

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/catalog/oauth/initiate",
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )

    state = response.json()["state"]
    record = store.get_oauth_state(state)
    assert record is not None
    assert record.server_id == "srv-1"
    assert record.code_challenge == code_challenge
    assert record.code_challenge_method == "S256"
    assert record.scopes == ["repo:read"]
    ttl_seconds = (record.expires_at - datetime.now(timezone.utc)).total_seconds()
    # TTL は 10 分前後になるはず。多少の時間経過を許容する。
    assert 500 <= ttl_seconds <= 610


@pytest.mark.asyncio
async def test_oauth_start_alias_endpoint_returns_state(reset_oauth_service):
    code_verifier = "alias-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/oauth/start",
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["state"]
    assert data["auth_url"].startswith("https://auth.example.com/authorize")
    assert f"code_challenge={code_challenge}" in data["auth_url"]


@pytest.mark.asyncio
async def test_oauth_start_returns_404_for_unknown_server(reset_oauth_service):
    code_verifier = "unknown-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/oauth/start",
            json={
                "server_id": "missing-server",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_oauth_start_rejects_non_s256_method(reset_oauth_service):
    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/oauth/start",
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "plain",
            },
        )

    assert response.status_code == 400
    body = response.json()
    assert "S256" in body["detail"]["message"]


@pytest.mark.asyncio
async def test_oauth_callback_pkce_mismatch_returns_400(reset_oauth_service):
    code_verifier = "correct-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        init_resp = await ac.post(
            "/api/oauth/start",
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        state = init_resp.json()["state"]

        callback_resp = await ac.get(
            "/api/oauth/callback",
            params={
                "code": "auth-code",
                "state": state,
                "code_verifier": "mismatched-verifier",
            },
        )

    assert callback_resp.status_code == 400
    body = callback_resp.json()
    assert body["error_code"] == "pkce_verification_failed"
    assert "code_verifier" in body["message"]


@pytest.mark.asyncio
async def test_oauth_callback_state_mismatch_returns_401(reset_oauth_service):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(
            "/api/catalog/oauth/callback",
            params={"code": "abc", "state": "invalid"},
        )

    assert response.status_code == 401
    assert "state" in response.json()["message"]


@pytest.mark.asyncio
async def test_oauth_callback_rejects_expired_state(reset_oauth_service):
    store = reset_oauth_service.state_store
    now = datetime.now(timezone.utc)
    expired = OAuthStateRecord(
        state="expired-state",
        server_id="srv-1",
        code_challenge="challenge",
        code_challenge_method="S256",
        scopes=["repo:read"],
        authorize_url="https://auth.example.com/authorize",
        token_url="https://auth.example.com/token",
        client_id="client-123",
        redirect_uri="http://localhost:8000/api/catalog/oauth/callback",
        expires_at=now - timedelta(seconds=1),
        created_at=now - timedelta(minutes=1),
    )
    store.save_oauth_state(expired)
    reset_oauth_service._state_store_mem.clear()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(
            "/api/catalog/oauth/callback",
            params={
                "code": "auth-code",
                "state": "expired-state",
                "code_verifier": "verifier",
            },
        )

    assert response.status_code == 401
    assert response.json()["error_code"] == "state_mismatch"


@pytest.mark.asyncio
async def test_oauth_callback_provider_4xx_returns_400(monkeypatch, reset_oauth_service):
    from app.services import oauth as oauth_service_module

    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    class DummyClient:
        call_count = 0

        def __init__(self, *args, **kwargs):
            return

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
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        state = init_resp.json()["state"]

        response = await ac.get(
            "/api/catalog/oauth/callback",
            params={
                "code": "auth-code",
                "state": state,
                "code_verifier": code_verifier,
            },
        )

    assert response.status_code == 400
    assert "再認可" in response.json()["message"]
    assert DummyClient.call_count == 1


@pytest.mark.asyncio
async def test_oauth_callback_provider_5xx_retries_then_502(monkeypatch, reset_oauth_service):
    from app.services import oauth as oauth_service_module

    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    class FailingClient:
        call_count = 0

        def __init__(self, *args, **kwargs):
            return

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
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        state = init_resp.json()["state"]

        response = await ac.get(
            "/api/catalog/oauth/callback",
            params={
                "code": "auth-code",
                "state": state,
                "code_verifier": code_verifier,
            },
        )

    assert response.status_code == 502
    assert "プロバイダ障害" in response.json()["message"]
    assert FailingClient.call_count == 3


@pytest.mark.asyncio
async def test_oauth_callback_success_returns_status(monkeypatch, reset_oauth_service):
    from app.services import oauth as oauth_service_module

    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    class SuccessClient:
        call_count = 0

        def __init__(self, *args, **kwargs):
            return

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
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        state = init_resp.json()["state"]

        response = await ac.get(
            "/api/catalog/oauth/callback",
            params={
                "code": "auth-code",
                "state": state,
                "code_verifier": code_verifier,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "authorized"
    assert body["credential_key"]
    assert "expires_at" in body
    assert SuccessClient.call_count == 1


@pytest.mark.asyncio
async def test_oauth_callback_consumes_persisted_state(monkeypatch, reset_oauth_service):
    from app.services import oauth as oauth_service_module

    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    class SuccessClient:
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

    monkeypatch.setattr(oauth_service_module.httpx, "AsyncClient", SuccessClient)
    store = reset_oauth_service.state_store

    async with AsyncClient(app=app, base_url="http://test") as ac:
        init_resp = await ac.post(
            "/api/catalog/oauth/initiate",
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        state = init_resp.json()["state"]

        # メモリキャッシュをクリアしても永続化された state から復旧できることを確認
        reset_oauth_service._state_store_mem.clear()

        callback_resp = await ac.get(
            "/api/catalog/oauth/callback",
            params={
                "code": "auth-code",
                "state": state,
                "code_verifier": code_verifier,
            },
        )

    assert callback_resp.status_code == 200
    assert store.get_oauth_state(state) is None


@pytest.mark.asyncio
async def test_oauth_callback_saves_credential_and_returns_key(
    monkeypatch, reset_oauth_service
):
    from app.services import oauth as oauth_service_module

    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    class SuccessClient:
        call_count = 0

        def __init__(self, *args, **kwargs):
            return

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
    store = reset_oauth_service.state_store

    async with AsyncClient(app=app, base_url="http://test") as ac:
        init_resp = await ac.post(
            "/api/catalog/oauth/initiate",
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        state = init_resp.json()["state"]

        response = await ac.get(
            "/api/catalog/oauth/callback",
            params={
                "code": "auth-code",
                "state": state,
                "code_verifier": code_verifier,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["credential_key"]
    record = store.get_credential(body["credential_key"])
    assert record is not None
    assert record.server_id == "srv-1"
    assert record.scopes == ["repo:read"]
    assert SuccessClient.call_count == 1


@pytest.mark.asyncio
async def test_oauth_tokens_persist_and_reload(monkeypatch, reset_oauth_service):
    from app.services import oauth as oauth_service_module

    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    class SuccessClient:
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

    monkeypatch.setattr(oauth_service_module.httpx, "AsyncClient", SuccessClient)
    store = reset_oauth_service.state_store

    async with AsyncClient(app=app, base_url="http://test") as ac:
        init_resp = await ac.post(
            "/api/catalog/oauth/initiate",
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        state = init_resp.json()["state"]

        response = await ac.get(
            "/api/catalog/oauth/callback",
            params={
                "code": "auth-code",
                "state": state,
                "code_verifier": code_verifier,
            },
        )

    cred_key = response.json()["credential_key"]
    reloaded = oauth_service_module.OAuthService(
        state_store=store,
        permitted_scopes=["repo:read"],
        credential_creator="test-admin",
    )

    assert cred_key in reloaded._secret_store
    secret = reloaded._secret_store[cred_key]
    assert secret["access_token"] == "token"
    assert secret["refresh_token"] == "refresh"


def test_oauth_removes_legacy_token_ref(reset_oauth_service):
    """blob が無い旧フォーマットを検出し再認可を促す。"""
    from app.services import oauth as oauth_service_module

    store = reset_oauth_service.state_store
    legacy = CredentialRecord(
        credential_key="legacy",
        token_ref={"type": "encrypted", "key": "legacy"},
        scopes=["repo:read"],
        expires_at=datetime.now(timezone.utc),
        server_id="srv-1",
        created_by="test-admin",
    )
    store.save_credential(legacy)

    reloaded = oauth_service_module.OAuthService(
        state_store=store,
        permitted_scopes=["repo:read"],
        credential_creator="test-admin",
    )

    assert store.get_credential("legacy") is None
    assert "legacy" not in reloaded._secret_store


@pytest.mark.asyncio
async def test_oauth_refresh_rotates_token_when_expiring(monkeypatch, reset_oauth_service):
    from app.services import oauth as oauth_service_module

    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    class RefreshClient:
        call_count = 0

        def __init__(self, *args, **kwargs):
            return

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None, headers=None, timeout=None):
            RefreshClient.call_count += 1
            if RefreshClient.call_count == 1:
                return httpx.Response(
                    status_code=200,
                    request=httpx.Request("POST", url),
                    json={
                        "access_token": "token-old",
                        "refresh_token": "refresh-old",
                        "expires_in": 60,
                        "scope": "repo:read",
                    },
                )
            return httpx.Response(
                status_code=200,
                request=httpx.Request("POST", url),
                json={
                    "access_token": "token-new",
                    "refresh_token": "refresh-new",
                    "expires_in": 7200,
                    "scope": "repo:read",
                },
            )

    monkeypatch.setattr(oauth_service_module.httpx, "AsyncClient", RefreshClient)
    store = reset_oauth_service.state_store

    async with AsyncClient(app=app, base_url="http://test") as ac:
        init_resp = await ac.post(
            "/api/catalog/oauth/initiate",
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        state = init_resp.json()["state"]
        callback_resp = await ac.get(
            "/api/catalog/oauth/callback",
            params={
                "code": "auth-code",
                "state": state,
                "code_verifier": code_verifier,
            },
        )
        cred_key = callback_resp.json()["credential_key"]

        refresh_resp = await ac.post(
            "/api/catalog/oauth/refresh",
            json={"server_id": "srv-1", "credential_key": cred_key},
        )

    assert refresh_resp.status_code == 200
    body = refresh_resp.json()
    assert body["refreshed"] is True
    assert body["credential_key"] != cred_key
    assert store.get_credential(cred_key) is None
    new_record = store.get_credential(body["credential_key"])
    assert new_record is not None
    assert new_record.scopes == ["repo:read"]
    assert RefreshClient.call_count == 2


@pytest.mark.asyncio
async def test_oauth_refresh_keeps_old_credential_when_save_fails(
    monkeypatch, reset_oauth_service
):
    from app.services import oauth as oauth_service_module

    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    class RefreshClient:
        call_count = 0

        def __init__(self, *args, **kwargs):
            return

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None, headers=None, timeout=None):
            RefreshClient.call_count += 1
            if RefreshClient.call_count == 1:
                return httpx.Response(
                    status_code=200,
                    request=httpx.Request("POST", url),
                    json={
                        "access_token": "token-old",
                        "refresh_token": "refresh-old",
                        "expires_in": 60,
                        "scope": "repo:read",
                    },
                )
            return httpx.Response(
                status_code=200,
                request=httpx.Request("POST", url),
                json={
                    "access_token": "token-new",
                    "refresh_token": "refresh-new",
                    "expires_in": 7200,
                    "scope": "repo:read",
                },
            )

    monkeypatch.setattr(oauth_service_module.httpx, "AsyncClient", RefreshClient)
    store = reset_oauth_service.state_store

    async with AsyncClient(app=app, base_url="http://test") as ac:
        init_resp = await ac.post(
            "/api/catalog/oauth/initiate",
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        state = init_resp.json()["state"]
        callback_resp = await ac.get(
            "/api/catalog/oauth/callback",
            params={
                "code": "auth-code",
                "state": state,
                "code_verifier": code_verifier,
            },
        )
        cred_key = callback_resp.json()["credential_key"]

        def failing_save_tokens(*args, **kwargs):
            raise RuntimeError("save failed")

        monkeypatch.setattr(reset_oauth_service, "_save_tokens", failing_save_tokens)

        with pytest.raises(RuntimeError):
            await reset_oauth_service.refresh_token(
                server_id="srv-1", credential_key=cred_key
            )

    assert store.get_credential(cred_key) is not None
    assert RefreshClient.call_count == 2


@pytest.mark.asyncio
async def test_oauth_refresh_invalid_grant_deletes_credential(
    monkeypatch, reset_oauth_service
):
    from app.services import oauth as oauth_service_module

    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    class InvalidGrantClient:
        call_count = 0

        def __init__(self, *args, **kwargs):
            return

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None, headers=None, timeout=None):
            InvalidGrantClient.call_count += 1
            if InvalidGrantClient.call_count == 1:
                return httpx.Response(
                    status_code=200,
                    request=httpx.Request("POST", url),
                    json={
                        "access_token": "token-old",
                        "refresh_token": "refresh-old",
                        "expires_in": 60,
                        "scope": "repo:read",
                    },
                )
            return httpx.Response(
                status_code=400,
                request=httpx.Request("POST", url),
                json={"error": "invalid_grant"},
            )

    monkeypatch.setattr(oauth_service_module.httpx, "AsyncClient", InvalidGrantClient)
    store = reset_oauth_service.state_store

    async with AsyncClient(app=app, base_url="http://test") as ac:
        init_resp = await ac.post(
            "/api/catalog/oauth/initiate",
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        state = init_resp.json()["state"]
        callback_resp = await ac.get(
            "/api/catalog/oauth/callback",
            params={
                "code": "auth-code",
                "state": state,
                "code_verifier": code_verifier,
            },
        )
        cred_key = callback_resp.json()["credential_key"]

        refresh_resp = await ac.post(
            "/api/catalog/oauth/refresh",
            json={"server_id": "srv-1", "credential_key": cred_key},
        )

    assert refresh_resp.status_code == 401
    assert "再認可" in refresh_resp.json()["message"]
    assert store.get_credential(cred_key) is None
    assert InvalidGrantClient.call_count == 2


@pytest.mark.asyncio
async def test_oauth_refresh_provider_5xx_keeps_credential(
    monkeypatch, reset_oauth_service
):
    from app.services import oauth as oauth_service_module

    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    class FailingRefreshClient:
        call_count = 0

        def __init__(self, *args, **kwargs):
            return

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None, headers=None, timeout=None):
            FailingRefreshClient.call_count += 1
            if FailingRefreshClient.call_count == 1:
                return httpx.Response(
                    status_code=200,
                    request=httpx.Request("POST", url),
                    json={
                        "access_token": "token-old",
                        "refresh_token": "refresh-old",
                        "expires_in": 60,
                        "scope": "repo:read",
                    },
                )
            return httpx.Response(
                status_code=500,
                request=httpx.Request("POST", url),
                json={"error": "server_error"},
            )

    async def immediate_sleep(seconds):
        return None

    monkeypatch.setattr(oauth_service_module.httpx, "AsyncClient", FailingRefreshClient)
    monkeypatch.setattr(oauth_service_module.asyncio, "sleep", immediate_sleep)
    store = reset_oauth_service.state_store

    async with AsyncClient(app=app, base_url="http://test") as ac:
        init_resp = await ac.post(
            "/api/catalog/oauth/initiate",
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        state = init_resp.json()["state"]
        callback_resp = await ac.get(
            "/api/catalog/oauth/callback",
            params={
                "code": "auth-code",
                "state": state,
                "code_verifier": code_verifier,
            },
        )
        cred_key = callback_resp.json()["credential_key"]

        refresh_resp = await ac.post(
            "/api/catalog/oauth/refresh",
            json={"server_id": "srv-1", "credential_key": cred_key},
        )

    assert refresh_resp.status_code == 503
    assert "プロバイダ障害" in refresh_resp.json()["message"]
    assert store.get_credential(cred_key) is not None
    assert FailingRefreshClient.call_count == 3


@pytest.mark.asyncio
async def test_oauth_refresh_server_id_mismatch_returns_422(monkeypatch, reset_oauth_service):
    from app.services import oauth as oauth_service_module

    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    class SuccessClient:
        call_count = 0

        def __init__(self, *args, **kwargs):
            return

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

    store = reset_oauth_service.state_store
    monkeypatch.setattr(oauth_service_module.httpx, "AsyncClient", SuccessClient)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        init_resp = await ac.post(
            "/api/catalog/oauth/initiate",
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        state = init_resp.json()["state"]

        callback_resp = await ac.get(
            "/api/catalog/oauth/callback",
            params={
                "code": "auth-code",
                "state": state,
                "code_verifier": code_verifier,
            },
        )
        cred_key = callback_resp.json()["credential_key"]

        refresh_resp = await ac.post(
            "/api/catalog/oauth/refresh",
            json={"server_id": "srv-2", "credential_key": cred_key},
        )

    assert refresh_resp.status_code == 422
    assert "server_id" in refresh_resp.json().get("detail", "")
    assert store.get_credential(cred_key) is not None


@pytest.mark.asyncio
async def test_oauth_initiate_rejects_unpermitted_scope(monkeypatch, reset_oauth_service):
    from app.services import oauth as oauth_service_module

    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/catalog/oauth/initiate",
            json={
                "server_id": "srv-1",
                "scopes": ["repo:admin"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )

    assert response.status_code == 400
    logs = reset_oauth_service.state_store.get_recent_audit_logs(limit=1)
    assert logs
    assert logs[0].action == "scope_denied"


def test_scope_update_requires_admin(reset_oauth_service):
    store = reset_oauth_service.state_store

    with pytest.raises(ScopeUpdateForbiddenError):
        reset_oauth_service.update_permitted_scopes(["repo:write"], is_admin=False)

    logs = store.get_recent_audit_logs(limit=1)
    assert logs
    assert logs[0].action == "scope_update_forbidden"


def test_expires_in_parsing(reset_oauth_service):
    service = reset_oauth_service

    assert service._parse_expires_in(None) == 3600
    assert service._parse_expires_in("bad") == 3600
    assert service._parse_expires_in(-5) == 0
    assert service._parse_expires_in(0) == 0

    before = datetime.now(timezone.utc)
    result = service._save_tokens(
        server_id="srv-1",
        scopes=["repo:read"],
        payload={"access_token": "a", "refresh_token": "b", "expires_in": 0},
    )
    record = service.state_store.get_credential(result["credential_key"])
    assert record is not None
    assert (record.expires_at - before).total_seconds() <= 2


@pytest.mark.asyncio
async def test_scope_update_by_admin_invalidates_credentials(monkeypatch, reset_oauth_service):
    from app.services import oauth as oauth_service_module

    code_verifier = "test-verifier"
    code_challenge = OAuthService._compute_code_challenge(code_verifier)

    class SuccessClient:
        call_count = 0

        def __init__(self, *args, **kwargs):
            return

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
    store = reset_oauth_service.state_store

    async with AsyncClient(app=app, base_url="http://test") as ac:
        init_resp = await ac.post(
            "/api/catalog/oauth/initiate",
            json={
                "server_id": "srv-1",
                "scopes": ["repo:read"],
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        state = init_resp.json()["state"]
        callback_resp = await ac.get(
            "/api/catalog/oauth/callback",
            params={
                "code": "auth-code",
                "state": state,
                "server_id": "srv-1",
                "code_verifier": code_verifier,
            },
        )
        cred_key = callback_resp.json()["credential_key"]

    assert store.get_credential(cred_key) is not None

    reset_oauth_service.update_permitted_scopes(["repo:write"], is_admin=True)

    assert store.get_credential(cred_key) is None
    logs = store.get_recent_audit_logs(limit=1)
    assert logs
    assert logs[0].action == "scope_updated"
