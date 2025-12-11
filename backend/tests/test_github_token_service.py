"""GitHub トークン管理サービスのテスト。"""

from datetime import datetime, timedelta

import pytest

from app.models.auth import Session
from app.models.github_token import GitHubItemSummary
from app.services.github_token import GitHubTokenService
from app.services.secrets import SecretManager
from app.services.state_store import StateStore


class StubAuthService:
    """固定セッションを返す簡易スタブ。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def validate_session(self, session_id: str) -> bool:
        return session_id == self._session.session_id

    async def get_session(self, session_id: str) -> Session | None:
        if session_id == self._session.session_id:
            return self._session
        return None


class StubSecretManager(SecretManager):
    """任意の値を返すスタブ SecretManager。"""

    def __init__(self, value: str) -> None:
        super().__init__()
        self._value = value

    async def resolve_reference(self, reference: str, session_id: str, bw_session_key: str) -> str:  # type: ignore[override]
        return self._value


@pytest.mark.asyncio
async def test_save_and_get_active_token(tmp_path) -> None:
    """Bitwarden から保存したトークンが暗号化され、復号して取得できること。"""
    db_path = tmp_path / "state.db"
    store = StateStore(str(db_path))
    store.init_schema()

    now = datetime.now()
    session = Session(
        session_id="s1",
        user_email="user@example.com",
        bw_session_key="bw-session",
        created_at=now,
        expires_at=now + timedelta(hours=1),
        last_activity=now,
    )
    auth = StubAuthService(session)
    secret_manager = StubSecretManager("ghp_example_token")

    service = GitHubTokenService(
        state_store=store,
        secret_manager=secret_manager,
        auth_service=auth,  # type: ignore[arg-type]
    )

    status = await service.save_from_bitwarden("s1", item_id="item1", field="password")

    assert status.configured is True
    assert status.source == "bitwarden:item1:password"
    assert store.get_github_token() is not None
    assert service.get_active_token() == "ghp_example_token"


@pytest.mark.asyncio
async def test_search_items_uses_bitwarden_list(monkeypatch, tmp_path) -> None:
    """検索APIが Bitwarden の結果を整形して返すことを検証する。"""
    db_path = tmp_path / "state.db"
    store = StateStore(str(db_path))
    store.init_schema()

    now = datetime.now()
    session = Session(
        session_id="s1",
        user_email="user@example.com",
        bw_session_key="bw-session",
        created_at=now,
        expires_at=now + timedelta(hours=1),
        last_activity=now,
    )
    auth = StubAuthService(session)
    secret_manager = StubSecretManager("unused")

    async def fake_list(self, bw_session_key: str, query: str, limit: int):  # type: ignore[override]
        return [
            GitHubItemSummary(id="i1", name="sample", fields=["password", "username"], type="login")
        ]

    monkeypatch.setattr(GitHubTokenService, "_list_bitwarden_items", fake_list, raising=True)

    service = GitHubTokenService(
        state_store=store,
        secret_manager=secret_manager,
        auth_service=auth,  # type: ignore[arg-type]
    )

    results = await service.search_items("sample", session_id="s1", limit=5)

    assert len(results) == 1
    assert results[0].id == "i1"
    assert "password" in results[0].fields

