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
    async def test_duplicate_id_collision_handling(self, catalog_service, mock_settings):
        """Test that duplicate server IDs are handled by appending suffixes."""
        # Task 4: ID 衝突時に接尾辞を付けて一意性を保つ
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


class TestMaxPagesLimit:
    """Tests for maximum pages limit (Task 5)."""

    @pytest.mark.asyncio
    async def test_max_pages_reached(self, catalog_service, mock_settings):
        """Test that pagination stops after reaching max_pages."""
        # Set max_pages to 2
        mock_settings.catalog_official_max_pages = 2

        # Create 3 pages of data
        page1_servers = [create_mock_server("page1", i) for i in range(30)]
        page2_servers = [create_mock_server("page2", i) for i in range(30)]
        page3_servers = [create_mock_server("page3", i) for i in range(30)]

        responses = [
            create_mock_response(page1_servers, "cursor-page2"),
            create_mock_response(page2_servers, "cursor-page3"),
            create_mock_response(page3_servers),  # This should not be fetched
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

                # Verify only 2 pages were fetched
                assert mock_get.call_count == 2

                # Verify warning message was set
                assert catalog_service.warning is not None
                assert "Max pages (2) reached" in catalog_service.warning

                # Verify 60 items returned (2 pages * 30 items)
                assert len(result) == 60

    @pytest.mark.asyncio
    async def test_max_pages_warning_message(self, catalog_service, mock_settings):
        """Test warning message content when max pages reached."""
        mock_settings.catalog_official_max_pages = 1

        page1_servers = [create_mock_server("page1", i) for i in range(30)]
        responses = [
            create_mock_response(page1_servers, "cursor-page2"),
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

                # Verify result contains expected items from first page
                assert isinstance(result, list)
                assert len(result) == 30  # Only first page (max_pages=1)

                # Verify warning contains expected information
                warning = catalog_service.warning
                assert warning is not None
                assert "Max pages (1) reached" in warning
                assert "Returning 30 items" in warning
                assert "More items may be available" in warning

    @pytest.mark.asyncio
    async def test_no_warning_when_all_pages_fetched(self, catalog_service, mock_settings):
        """Test no warning when all pages are fetched within limit."""
        mock_settings.catalog_official_max_pages = 10

        page1_servers = [create_mock_server("page1", i) for i in range(30)]
        page2_servers = [create_mock_server("page2", i) for i in range(30)]

        responses = [
            create_mock_response(page1_servers, "cursor-page2"),
            create_mock_response(page2_servers),  # Last page, no cursor
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

                # Verify no warning when all pages fetched
                assert catalog_service.warning is None

                # Verify all items returned
                assert len(result) == 60


class TestTimeout:
    """Tests for overall timeout (Task 6)."""

    @pytest.mark.asyncio
    async def test_timeout_reached(self, catalog_service, mock_settings):
        """Test that pagination stops when timeout is reached."""
        # Set short timeout (1 second)
        mock_settings.catalog_official_fetch_timeout = 1

        page1_servers = [create_mock_server("page1", i) for i in range(30)]
        page2_servers = [create_mock_server("page2", i) for i in range(30)]

        responses = [
            create_mock_response(page1_servers, "cursor-page2"),
            create_mock_response(page2_servers, "cursor-page3"),
        ]

        with patch.object(catalog_service, "_url_validator") as mock_validator:
            mock_validator.validate.return_value = mock_settings.catalog_official_url

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # Mock time to simulate timeout
                with patch("time.time") as mock_time:
                    # Start time: 0, after page 1: 0.5, after page 2: 1.5 (exceeds timeout)
                    mock_time.side_effect = [0, 0.5, 1.5]

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

                    # Verify only 1 page was fetched (timeout before page 2)
                    assert mock_get.call_count == 1

                    # Verify warning message was set
                    assert catalog_service.warning is not None
                    assert "Timeout reached" in catalog_service.warning
                    assert "after 1 pages" in catalog_service.warning

                    # Verify partial data returned (30 items from page 1)
                    assert len(result) == 30

    @pytest.mark.asyncio
    async def test_timeout_warning_message(self, catalog_service, mock_settings):
        """Test warning message content when timeout is reached."""
        mock_settings.catalog_official_fetch_timeout = 1

        page1_servers = [create_mock_server("page1", i) for i in range(30)]
        responses = [
            create_mock_response(page1_servers, "cursor-page2"),
        ]

        with patch.object(catalog_service, "_url_validator") as mock_validator:
            mock_validator.validate.return_value = mock_settings.catalog_official_url

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                with patch("time.time") as mock_time:
                    # Start time: 0, check after page 1: 0.5, check before page 2: 2.0 (timeout)
                    mock_time.side_effect = [0, 0.5, 2.0]

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

                    # Verify result contains items from first page before timeout
                    assert isinstance(result, list)
                    assert len(result) == 30  # Only first page before timeout

                    # Verify warning contains expected information
                    warning = catalog_service.warning
                    assert warning is not None
                    assert "Timeout reached" in warning
                    assert "Returning 30 items" in warning

    @pytest.mark.asyncio
    async def test_no_timeout_within_limit(self, catalog_service, mock_settings):
        """Test no timeout when all pages fetched within time limit."""
        mock_settings.catalog_official_fetch_timeout = 10

        page1_servers = [create_mock_server("page1", i) for i in range(30)]
        page2_servers = [create_mock_server("page2", i) for i in range(30)]

        responses = [
            create_mock_response(page1_servers, "cursor-page2"),
            create_mock_response(page2_servers),
        ]

        with patch.object(catalog_service, "_url_validator") as mock_validator:
            mock_validator.validate.return_value = mock_settings.catalog_official_url

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                with patch("time.time") as mock_time:
                    mock_time.side_effect = [0, 0.5, 1.0]  # Within timeout

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

                    # Verify all pages fetched
                    assert mock_get.call_count == 2
                    assert catalog_service.warning is None
                    assert len(result) == 60


class TestErrorHandling:
    """Tests for error handling (Task 7)."""

    @pytest.mark.asyncio
    async def test_initial_page_failure(self, catalog_service, mock_settings):
        """Test that CatalogError is raised when initial page fetch fails."""
        with patch.object(catalog_service, "_url_validator") as mock_validator:
            mock_validator.validate.return_value = mock_settings.catalog_official_url

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_get = AsyncMock()
                # Simulate network error on first request
                mock_get.side_effect = httpx.ConnectError("Connection failed")
                mock_client.get = mock_get

                # Verify CatalogError is raised
                with pytest.raises(CatalogError) as exc_info:
                    await catalog_service._fetch_official_registry_with_pagination(
                        mock_settings.catalog_official_url
                    )

                assert exc_info.value.error_code == CatalogErrorCode.UPSTREAM_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_subsequent_page_failure_returns_partial_data(self, catalog_service, mock_settings):
        """Test that partial data is returned when subsequent page fetch fails."""
        page1_servers = [create_mock_server("page1", i) for i in range(30)]

        with patch.object(catalog_service, "_url_validator") as mock_validator:
            mock_validator.validate.return_value = mock_settings.catalog_official_url

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_get = AsyncMock()
                # First page succeeds, second page fails
                mock_get.side_effect = [
                    MagicMock(
                        status_code=200,
                        json=MagicMock(return_value=create_mock_response(page1_servers, "cursor-page2")),
                        raise_for_status=MagicMock()
                    ),
                    httpx.ConnectError("Connection failed on page 2")
                ]
                mock_client.get = mock_get

                result = await catalog_service._fetch_official_registry_with_pagination(
                    mock_settings.catalog_official_url
                )

                # Verify partial data returned (30 items from page 1)
                assert len(result) == 30

                # Verify warning message was set
                assert catalog_service.warning is not None
                assert "Error fetching page 2" in catalog_service.warning
                assert "Returning 30 items" in catalog_service.warning

    @pytest.mark.asyncio
    async def test_rate_limit_429_without_partial_data(self, catalog_service, mock_settings):
        """Test that 429 error is raised when rate limited on initial page."""
        with patch.object(catalog_service, "_url_validator") as mock_validator:
            mock_validator.validate.return_value = mock_settings.catalog_official_url

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_get = AsyncMock()
                # Simulate 429 rate limit on first request
                mock_response = MagicMock()
                mock_response.status_code = 429
                mock_response.headers = {"Retry-After": "60"}
                mock_get.side_effect = httpx.HTTPStatusError(
                    "Rate limited",
                    request=MagicMock(),
                    response=mock_response
                )
                mock_client.get = mock_get

                # Verify CatalogError with RATE_LIMITED is raised
                with pytest.raises(CatalogError) as exc_info:
                    await catalog_service._fetch_official_registry_with_pagination(
                        mock_settings.catalog_official_url
                    )

                assert exc_info.value.error_code == CatalogErrorCode.RATE_LIMITED
                assert exc_info.value.retry_after_seconds == 60

    @pytest.mark.asyncio
    async def test_rate_limit_429_with_partial_data(self, catalog_service, mock_settings):
        """Test that 429 error is raised even when partial data exists."""
        page1_servers = [create_mock_server("page1", i) for i in range(30)]

        with patch.object(catalog_service, "_url_validator") as mock_validator:
            mock_validator.validate.return_value = mock_settings.catalog_official_url

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_get = AsyncMock()
                # First page succeeds, second page rate limited
                mock_response = MagicMock()
                mock_response.status_code = 429
                mock_response.headers = {"Retry-After": "60"}
                mock_get.side_effect = [
                    MagicMock(
                        status_code=200,
                        json=MagicMock(return_value=create_mock_response(page1_servers, "cursor-page2")),
                        raise_for_status=MagicMock()
                    ),
                    httpx.HTTPStatusError(
                        "Rate limited",
                        request=MagicMock(),
                        response=mock_response
                    )
                ]
                mock_client.get = mock_get

                # Verify CatalogError with RATE_LIMITED is raised
                with pytest.raises(CatalogError) as exc_info:
                    await catalog_service._fetch_official_registry_with_pagination(
                        mock_settings.catalog_official_url
                    )

                assert exc_info.value.error_code == CatalogErrorCode.RATE_LIMITED

    @pytest.mark.asyncio
    async def test_http_error_with_partial_data(self, catalog_service, mock_settings):
        """Test partial success with HTTP error on subsequent page."""
        page1_servers = [create_mock_server("page1", i) for i in range(30)]

        with patch.object(catalog_service, "_url_validator") as mock_validator:
            mock_validator.validate.return_value = mock_settings.catalog_official_url

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_get = AsyncMock()
                # First page succeeds, second page returns 503
                mock_response = MagicMock()
                mock_response.status_code = 503
                mock_get.side_effect = [
                    MagicMock(
                        status_code=200,
                        json=MagicMock(return_value=create_mock_response(page1_servers, "cursor-page2")),
                        raise_for_status=MagicMock()
                    ),
                    httpx.HTTPStatusError(
                        "Service unavailable",
                        request=MagicMock(),
                        response=mock_response
                    )
                ]
                mock_client.get = mock_get

                result = await catalog_service._fetch_official_registry_with_pagination(
                    mock_settings.catalog_official_url
                )

                # Verify partial data returned
                assert len(result) == 30

                # Verify warning message
                assert catalog_service.warning is not None
                assert "Error fetching page 2" in catalog_service.warning
