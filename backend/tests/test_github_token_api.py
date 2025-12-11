"""GitHub トークン API のテスト。"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.github_token import get_github_token_service
from app.main import app
from app.models.github_token import GitHubItemSummary, GitHubTokenStatus
from app.services.github_token import GitHubTokenError

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    """テスト毎に依存関係の上書きをクリアする。"""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def auth_headers() -> dict[str, str]:
    """セッションIDを含むヘッダーを返す。"""
    return {"Authorization": "Bearer s1"}


class StubGitHubTokenService:
    """同期/非同期メソッドを混在させた軽量スタブ。"""

    def __init__(self) -> None:
        self._status = GitHubTokenStatus(
            configured=True,
            source="bitwarden:item:password",
            updated_by="user@example.com",
            updated_at=datetime(2024, 1, 1),
        )
        self.search_items = AsyncMock()
        self.save_from_bitwarden = AsyncMock()
        self.delete_token = AsyncMock(return_value=None)

    def set_status(self, status: GitHubTokenStatus) -> None:
        self._status = status

    def get_status(self) -> GitHubTokenStatus:
        return self._status


def test_status_returns_configured_flag() -> None:
    """ステータス取得が保存状況を返すこと。"""
    service = StubGitHubTokenService()
    app.dependency_overrides[get_github_token_service] = lambda: service

    response = client.get("/api/github-token/status", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert "source" in body


def test_search_returns_items() -> None:
    """検索 API がアイテム一覧を返すこと。"""
    service = StubGitHubTokenService()
    service.search_items.return_value = [
        GitHubItemSummary(id="i1", name="sample", fields=["password"], type="login")
    ]
    app.dependency_overrides[get_github_token_service] = lambda: service

    response = client.get("/api/github-token/search", params={"query": "sample"}, headers=auth_headers())

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["id"] == "i1"


def test_search_handles_bitwarden_error() -> None:
    """Bitwarden エラー時に 400 を返すこと。"""
    service = StubGitHubTokenService()
    service.search_items.side_effect = GitHubTokenError("failed")
    app.dependency_overrides[get_github_token_service] = lambda: service

    response = client.get("/api/github-token/search", params={"query": "fail"}, headers=auth_headers())

    assert response.status_code == 400


def test_save_token_success() -> None:
    """保存 API が成功レスポンスを返すこと。"""
    service = StubGitHubTokenService()
    service.save_from_bitwarden.return_value = GitHubTokenStatus(
        configured=True,
        source="bitwarden:item:password",
        updated_by="user@example.com",
        updated_at=datetime(2024, 1, 1),
    )
    app.dependency_overrides[get_github_token_service] = lambda: service

    response = client.post(
        "/api/github-token",
        json={"item_id": "item", "field": "password"},
        headers=auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"]["configured"] is True

