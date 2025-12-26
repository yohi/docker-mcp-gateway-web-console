"""Tests for Official Registry pagination logic."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.catalog import CatalogErrorCode
from app.services.catalog import CatalogError, CatalogService


@pytest.fixture
def catalog_service():
    """Create a CatalogService instance for testing."""
    return CatalogService()


@pytest.fixture
def mock_settings():
    """Mock settings for pagination tests."""
    with patch("app.services.catalog.settings") as mock:
        mock.catalog_official_url = "https://registry.modelcontextprotocol.io/v0/servers"
        mock.catalog_official_max_pages = 20
        mock.catalog_official_fetch_timeout = 60
        mock.catalog_official_page_delay = 100
        yield mock


def create_mock_response(servers: list, next_cursor: str | None = None) -> dict:
    """Create a mock Official Registry response."""
    response = {
        "servers": servers,
        "metadata": {
            "count": len(servers)
        }
    }
    if next_cursor:
        response["metadata"]["nextCursor"] = next_cursor
    return response


def create_mock_server(name: str, index: int) -> dict:
    """Create a mock server entry for Official Registry."""
    return {
        "server": {
            "name": f"{name}-{index}",
            "display_name": f"Server {name} {index}",
            "description": f"Test server {name} {index}",
            "packages": [
                {
                    "identifier": f"test/{name}:{index}",
                    "registryType": "oci"
                }
            ]
        },
        "_meta": {}
    }


class TestFetchOfficialRegistryWithPagination:
    """Tests for _fetch_official_registry_with_pagination method."""

    @pytest.mark.asyncio
    async def test_single_page_no_cursor(self, catalog_service, mock_settings):
        """Test fetching a single page with no nextCursor."""
        # Task 2: 初回リクエストをカーソルなしで発行する
        servers = [create_mock_server("test", i) for i in range(30)]
        mock_response = create_mock_response(servers)

        with patch.object(catalog_service, "_url_validator") as mock_validator:
            mock_validator.validate.return_value = mock_settings.catalog_official_url

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_get = AsyncMock()
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = mock_response
                mock_get.return_value.raise_for_status = MagicMock()
                mock_client.get = mock_get

                # This should work after implementation
                result = await catalog_service._fetch_official_registry_with_pagination(
                    mock_settings.catalog_official_url
                )

                # Verify single request without cursor
                assert mock_get.call_count == 1
                assert len(result) == 30

    @pytest.mark.asyncio
    async def test_multiple_pages_with_cursor(self, catalog_service, mock_settings):
        """Test fetching multiple pages with nextCursor."""
        # Task 2: カーソルが存在する場合、次ページを取得する
        page1_servers = [create_mock_server("page1", i) for i in range(30)]
        page2_servers = [create_mock_server("page2", i) for i in range(30)]
        page3_servers = [create_mock_server("page3", i) for i in range(30)]

        responses = [
            create_mock_response(page1_servers, "cursor-page2"),
            create_mock_response(page2_servers, "cursor-page3"),
            create_mock_response(page3_servers),  # Last page, no cursor
        ]

        with patch.object(catalog_service, "_url_validator") as mock_validator:
            mock_validator.validate.return_value = mock_settings.catalog_official_url

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_get = AsyncMock()
                mock_get.side_effect = [
                    MagicMock(
                        status_code=200,
                        json=MagicMock(return_value=resp),
                        raise_for_status=MagicMock()
                    )
                    for resp in responses
                ]
                mock_client.get = mock_get

                result = await catalog_service._fetch_official_registry_with_pagination(
                    mock_settings.catalog_official_url
                )

                # Verify three requests with correct cursors
                assert mock_get.call_count == 3

                # Check first request (no cursor)
                first_call_url = mock_get.call_args_list[0][0][0]
                assert "cursor=" not in first_call_url

                # Check second request (with cursor-page2)
                second_call_url = mock_get.call_args_list[1][0][0]
                assert "cursor=cursor-page2" in second_call_url

                # Check third request (with cursor-page3)
                third_call_url = mock_get.call_args_list[2][0][0]
                assert "cursor=cursor-page3" in third_call_url

                # Verify all servers are combined (90 total)
                assert len(result) == 90

    @pytest.mark.asyncio
    async def test_page_delay(self, catalog_service, mock_settings):
        """Test page delay between requests."""
        # Task 3: 各ページ取得後に遅延を挿入する
        mock_settings.catalog_official_page_delay = 100  # 100ms

        page1_servers = [create_mock_server("page1", i) for i in range(30)]
        page2_servers = [create_mock_server("page2", i) for i in range(30)]

        responses = [
            create_mock_response(page1_servers, "cursor-page2"),
            create_mock_response(page2_servers),  # Last page
        ]

        with patch.object(catalog_service, "_url_validator") as mock_validator:
            mock_validator.validate.return_value = mock_settings.catalog_official_url

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_get = AsyncMock()
                mock_get.side_effect = [
                    MagicMock(
                        status_code=200,
                        json=MagicMock(return_value=resp),
                        raise_for_status=MagicMock()
                    )
                    for resp in responses
                ]
                mock_client.get = mock_get

                with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                    result = await catalog_service._fetch_official_registry_with_pagination(
                        mock_settings.catalog_official_url
                    )

                    # Verify sleep was called once (after page 1, before page 2)
                    assert mock_sleep.call_count == 1
                    # Verify sleep duration is 0.1 seconds (100ms)
                    mock_sleep.assert_called_with(0.1)

                    # Verify all servers are returned
                    assert len(result) == 60

    @pytest.mark.asyncio
    async def test_no_delay_on_last_page(self, catalog_service, mock_settings):
        """Test that delay is skipped on the last page."""
        # Task 3: 最終ページ(カーソルなし)の場合は遅延をスキップする
        servers = [create_mock_server("test", i) for i in range(30)]
        mock_response = create_mock_response(servers)  # No cursor

        with patch.object(catalog_service, "_url_validator") as mock_validator:
            mock_validator.validate.return_value = mock_settings.catalog_official_url

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_get = AsyncMock()
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = mock_response
                mock_get.return_value.raise_for_status = MagicMock()
                mock_client.get = mock_get

                with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                    result = await catalog_service._fetch_official_registry_with_pagination(
                        mock_settings.catalog_official_url
                    )

                    # Verify no sleep on last page
                    assert mock_sleep.call_count == 0
                    assert len(result) == 30

    @pytest.mark.asyncio
    async def test_duplicate_removal(self, catalog_service, mock_settings):
        """Test that duplicate servers are removed based on ID."""
        # Task 4: ID ベースの重複除外を実装する
        # Create pages with some duplicate servers
        page1_servers = [
            create_mock_server("test", 1),
            create_mock_server("test", 2),
            create_mock_server("test", 3),
        ]
        page2_servers = [
            create_mock_server("test", 2),  # Duplicate from page 1
            create_mock_server("test", 4),
            create_mock_server("test", 5),
        ]

        responses = [
            create_mock_response(page1_servers, "cursor-page2"),
            create_mock_response(page2_servers),
        ]

        with patch.object(catalog_service, "_url_validator") as mock_validator:
            mock_validator.validate.return_value = mock_settings.catalog_official_url

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_get = AsyncMock()
                mock_get.side_effect = [
                    MagicMock(
                        status_code=200,
                        json=MagicMock(return_value=resp),
                        raise_for_status=MagicMock()
                    )
                    for resp in responses
                ]
                mock_client.get = mock_get

                result = await catalog_service._fetch_official_registry_with_pagination(
                    mock_settings.catalog_official_url
                )

                # Verify duplicate names get unique IDs (test-2 becomes test-2 and test-2-2)
                assert len(result) == 6

                # Verify all unique IDs are present (test-2 from page 1, test-2-2 from page 2)
                result_ids = sorted([item.id for item in result])
                expected_ids = sorted(["test-1", "test-2", "test-2-2", "test-3", "test-4", "test-5"])
                assert result_ids == expected_ids
