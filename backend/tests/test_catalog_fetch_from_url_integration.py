"""Tests for _fetch_from_url integration with Official Registry pagination."""

import pytest
from unittest.mock import AsyncMock, patch

from app.config import settings
from app.models.catalog import CatalogItem
from app.services.catalog import CatalogService


@pytest.fixture
def catalog_service(monkeypatch):
    """Create a fresh CatalogService instance for each test."""
    # Set test URLs in settings
    # AllowedURLsValidator will automatically include:
    # - catalog_default_url
    # - catalog_official_url
    # - catalog_docker_url (alias of catalog_default_url)
    monkeypatch.setattr(
        settings, "catalog_default_url", "https://example.com/other-catalog.json"
    )
    monkeypatch.setattr(
        settings, "catalog_official_url", "https://registry.modelcontextprotocol.io/v0/servers"
    )
    return CatalogService()


@pytest.mark.asyncio
async def test_fetch_from_url_calls_pagination_for_official_url(catalog_service, monkeypatch):
    """
    _fetch_from_url が Official Registry URL の場合に
    _fetch_official_registry_with_pagination を呼び出すことを確認する。
    """
    # Setup: Mock the pagination method
    mock_pagination = AsyncMock(return_value=[
        CatalogItem(
            id="test-server",
            name="Test Server",
            description="A test server",
            vendor="Test",
            category="general",
            docker_image="test/server:latest",
            default_env={},
            required_envs=[],
            required_secrets=[]
        )
    ])

    with patch.object(
        catalog_service,
        '_fetch_official_registry_with_pagination',
        mock_pagination
    ):
        # Execute: Call _fetch_from_url with Official Registry URL
        result = await catalog_service._fetch_from_url(settings.catalog_official_url)

        # Assert: Pagination method was called
        mock_pagination.assert_called_once_with(settings.catalog_official_url)

        # Assert: Result is returned correctly
        assert len(result) == 1
        assert result[0].id == "test-server"


@pytest.mark.asyncio
async def test_fetch_from_url_does_not_call_pagination_for_other_urls(catalog_service, monkeypatch):
    """
    _fetch_from_url が Official Registry 以外の URL の場合に
    _fetch_official_registry_with_pagination を呼び出さないことを確認する。
    """
    # Setup: Mock the pagination method to track calls
    mock_pagination = AsyncMock()

    # Setup: Mock httpx.AsyncClient to return a valid response
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = AsyncMock()
    mock_response.json.return_value = [
        {
            "name": "other-server",
            "description": "Other server",
            "vendor": "Other",
            "image": "other/server:latest",
            "required_envs": []
        }
    ]

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch.object(
        catalog_service,
        '_fetch_official_registry_with_pagination',
        mock_pagination
    ), patch('httpx.AsyncClient', return_value=mock_client):
        # Execute: Call _fetch_from_url with a different URL
        other_url = "https://example.com/other-catalog.json"
        result = await catalog_service._fetch_from_url(other_url)

        # Assert: Pagination method was NOT called
        mock_pagination.assert_not_called()

        # Assert: Result contains data from non-paginated fetch
        assert len(result) == 1
        assert result[0].id == "other-server"


@pytest.mark.asyncio
async def test_fetch_from_url_normalizes_url_before_comparison(catalog_service, monkeypatch):
    """
    _fetch_from_url が URL を正規化してから Official Registry URL と比較することを確認する。
    """
    # Setup: Mock the pagination method
    mock_pagination = AsyncMock(return_value=[
        CatalogItem(
            id="normalized-server",
            name="Normalized Server",
            description="A server from normalized URL",
            vendor="Test",
            category="general",
            docker_image="normalized/server:latest",
            default_env={},
            required_envs=[],
            required_secrets=[]
        )
    ])

    with patch.object(
        catalog_service,
        '_fetch_official_registry_with_pagination',
        mock_pagination
    ):
        # Execute: Call _fetch_from_url with Official URL that has trailing slash
        url_with_trailing_slash = settings.catalog_official_url + "/"
        result = await catalog_service._fetch_from_url(url_with_trailing_slash)

        # Assert: Pagination method was called (URL was normalized)
        # Note: AllowedURLsValidator should normalize the URL before comparison
        assert mock_pagination.call_count == 1

        # Assert: Result is returned correctly
        assert len(result) == 1
        assert result[0].id == "normalized-server"


@pytest.mark.asyncio
async def test_fetch_from_url_compares_normalized_official_url(catalog_service, monkeypatch):
    """
    _fetch_from_url が settings.catalog_official_url も正規化してから比較することを確認する。

    このテストは、settings.catalog_official_url に末尾スラッシュがある場合でも
    正しくマッチすることを確認する。
    """
    # Setup: Set official URL with trailing slash in settings
    monkeypatch.setattr(
        settings,
        "catalog_official_url",
        "https://registry.modelcontextprotocol.io/v0/servers/"  # Trailing slash
    )

    # Recreate service with new settings
    catalog_service_with_trailing = CatalogService()

    # Setup: Mock the pagination method
    mock_pagination = AsyncMock(return_value=[
        CatalogItem(
            id="trailing-slash-server",
            name="Trailing Slash Server",
            description="Server from URL with trailing slash",
            vendor="Test",
            category="general",
            docker_image="test/server:latest",
            default_env={},
            required_envs=[],
            required_secrets=[]
        )
    ])

    with patch.object(
        catalog_service_with_trailing,
        '_fetch_official_registry_with_pagination',
        mock_pagination
    ):
        # Execute: Call _fetch_from_url with Official URL WITHOUT trailing slash
        url_without_trailing_slash = "https://registry.modelcontextprotocol.io/v0/servers"
        result = await catalog_service_with_trailing._fetch_from_url(url_without_trailing_slash)

        # Assert: Pagination method was called (both URLs should be normalized and match)
        mock_pagination.assert_called_once()

        # Assert: Result is returned correctly
        assert len(result) == 1
        assert result[0].id == "trailing-slash-server"
