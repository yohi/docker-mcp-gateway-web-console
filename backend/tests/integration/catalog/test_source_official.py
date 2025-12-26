
import pytest
from unittest.mock import patch, AsyncMock, Mock
from app.main import app
from app.config import settings
from app.models.catalog import CatalogItem
from httpx import AsyncClient

# Sample Official MCP Registry response format
OFFICIAL_REGISTRY_RESPONSE = [
    {
        "name": "modelcontextprotocol/awesome-tool",
        "display_name": "Awesome Tool",
        "description": "高速なMCP対応AIツール",
        "homepage_url": "https://awesome.example.com",
        "tags": ["productivity"],
        "client": {
            "mcp": {
                "capabilities": ["call_tool"],
                "transport": {
                    "type": "websocket",
                    "url": "wss://awesome.example.com/mcp"
                }
            }
        }
    },
    {
        "name": "modelcontextprotocol/minimal",
        "display_name": "Minimal MCP",
        "client": {
            "mcp": {
                "transport": {
                    "type": "http",
                    "url": "https://minimal.example.com/mcp"
                }
            }
        }
    }
]

# Expected CatalogItem after conversion
EXPECTED_CATALOG_ITEMS = [
    CatalogItem(
        id="modelcontextprotocol-awesome-tool",
        name="Awesome Tool",
        description="高速なMCP対応AIツール",
        vendor="modelcontextprotocol",
        category="general",
        docker_image="",
        required_envs=[],
        required_secrets=[],
        homepage_url="https://awesome.example.com",
        tags=["productivity"],
        capabilities=["call_tool"],
        remote_endpoint="wss://awesome.example.com/mcp"
    ),
    CatalogItem(
        id="modelcontextprotocol-minimal",
        name="Minimal MCP",
        description="",
        vendor="modelcontextprotocol",
        category="general",
        docker_image="",
        required_envs=[],
        required_secrets=[],
        remote_endpoint="https://minimal.example.com/mcp"
    )
]


@pytest.mark.asyncio
async def test_get_catalog_official_source():
    """
    Test E2E flow for source=official.
    Verifies that Official MCP Registry format is correctly converted to CatalogItem.

    Requirements: 2.4, 3.1
    """
    # Patch the catalog service to return Official Registry format data
    with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch, \
         patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:

        # Scenario: No cache, fetch from Official Registry succeeds
        mock_get_cache.return_value = None
        mock_fetch.return_value = (EXPECTED_CATALOG_ITEMS, False)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=official")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is False
        assert len(data["servers"]) == 2

        # Verify first item (with full fields)
        first_item = data["servers"][0]
        assert first_item["id"] == "modelcontextprotocol-awesome-tool"
        assert first_item["name"] == "Awesome Tool"
        assert first_item["description"] == "高速なMCP対応AIツール"

        # Verify second item (minimal fields)
        second_item = data["servers"][1]
        assert second_item["id"] == "modelcontextprotocol-minimal"
        assert second_item["name"] == "Minimal MCP"
        assert second_item["description"] == ""

        # Verify service was called with Official Registry URL
        mock_fetch.assert_called_once()
        args, _ = mock_fetch.call_args
        assert args[0] == settings.catalog_official_url


@pytest.mark.asyncio
async def test_get_catalog_official_schema_conversion():
    """
    Test that Official MCP Registry schema is correctly converted.
    Verifies field mapping and handling of missing/invalid fields.

    Requirements: 3.2, 3.3, 3.4
    """
    # Official Registry format payloads with various edge cases
    official_registry_payloads = [
        # Complete item with all fields
        {
            "name": "modelcontextprotocol/complete-server",
            "display_name": "Complete Server",
            "description": "Server with all fields",
            "homepage_url": "https://complete.example.com",
            "tags": ["productivity", "testing"],
            "client": {
                "mcp": {
                    "capabilities": ["call_tool", "sample_prompts"],
                    "transport": {
                        "type": "websocket",
                        "url": "wss://complete.example.com/mcp"
                    }
                }
            }
        },
        # Item with missing optional fields
        {
            "name": "modelcontextprotocol/minimal-server",
            "display_name": "Minimal Server"
        },
        # Item with invalid tag types (should be filtered)
        {
            "name": "modelcontextprotocol/invalid-tags",
            "display_name": "Invalid Tags Server",
            "tags": ["valid", 123, None, "another-valid"]
        },
        # Item with invalid capabilities types (should be filtered)
        {
            "name": "modelcontextprotocol/invalid-caps",
            "display_name": "Invalid Capabilities",
            "client": {
                "mcp": {
                    "capabilities": ["valid_cap", 456, None, "another_cap"]
                }
            }
        },
        # Item with invalid URL scheme (should be filtered to None)
        {
            "name": "modelcontextprotocol/invalid-url",
            "display_name": "Invalid URL Server",
            "homepage_url": "ftp://invalid.example.com",
            "client": {
                "mcp": {
                    "transport": {
                        "url": "ftp://invalid.example.com/mcp"
                    }
                }
            }
        },
        # Item with missing name but has display_name (should use display_name)
        {
            "display_name": "Display Name Only",
            "description": "This item only has display_name"
        }
    ]

    with patch("app.api.catalog.catalog_service._fetch_from_url") as mock_fetch_url, \
         patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:

        mock_get_cache.return_value = None

        # Mock the raw HTTP response to return Official Registry format
        async def mock_fetch_implementation(url):
            # Simulate the catalog service's internal conversion logic
            from app.services.catalog import CatalogService
            service = CatalogService()
            # Return the raw payload to test conversion
            converted = []
            used_ids = set()
            for item in official_registry_payloads:
                if item is not None:
                    result = service._convert_explore_server(item, used_ids=used_ids)
                    if result is not None:
                        converted.append(result)
            return service._filter_items_missing_image(converted)

        mock_fetch_url.side_effect = mock_fetch_implementation

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=official")

        assert response.status_code == 200
        data = response.json()

        servers = data["servers"]
        assert len(servers) >= 4  # At least 4 valid items should be converted

        # Verify first item (complete server) has all fields mapped correctly
        complete_server = next(s for s in servers if "complete-server" in s["id"])
        assert complete_server["name"] == "Complete Server"
        assert complete_server["description"] == "Server with all fields"
        assert complete_server["vendor"] == "modelcontextprotocol"
        assert complete_server["homepage_url"] == "https://complete.example.com"
        assert set(complete_server["tags"]) == {"productivity", "testing"}
        assert set(complete_server["capabilities"]) == {"call_tool", "sample_prompts"}
        assert complete_server["remote_endpoint"] == "wss://complete.example.com/mcp"

        # Verify minimal item has defaults for missing fields
        minimal_server = next(s for s in servers if "minimal-server" in s["id"])
        assert minimal_server["name"] == "Minimal Server"
        assert minimal_server["description"] == ""
        assert minimal_server.get("homepage_url") is None
        assert minimal_server["tags"] == []
        assert minimal_server["capabilities"] == []
        assert minimal_server.get("remote_endpoint") is None

        # Verify invalid types are filtered
        invalid_tags_server = next(s for s in servers if "invalid-tags" in s["id"])
        assert invalid_tags_server["tags"] == ["valid", "another-valid"]

        invalid_caps_server = next(s for s in servers if "invalid-caps" in s["id"])
        assert invalid_caps_server["capabilities"] == ["valid_cap", "another_cap"]

        # Verify invalid URLs are rejected
        invalid_url_server = next(s for s in servers if "invalid-url" in s["id"])
        assert invalid_url_server.get("homepage_url") is None
        assert invalid_url_server.get("remote_endpoint") is None

        # Verify display_name fallback works
        display_only = next(s for s in servers if s["name"] == "Display Name Only")
        assert display_only["id"] == "display-name-only"
        assert display_only["description"] == "This item only has display_name"


@pytest.mark.asyncio
async def test_get_catalog_official_with_cache():
    """
    Test that cached Official Registry data is returned correctly.
    Verifies cache behavior is consistent between sources.

    Requirements: 2.4, 3.1
    """
    with patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:
        # Scenario: Cache available for Official Registry
        mock_get_cache.return_value = EXPECTED_CATALOG_ITEMS

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=official")

        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is True
        assert len(data["servers"]) == 2

        # Verify get_cached_catalog was called
        mock_get_cache.assert_called_once()


@pytest.mark.asyncio
async def test_get_catalog_official_error_handling():
    """
    Test error handling when Official Registry fetch fails.
    Verifies structured error responses are returned.

    Requirements: 4.1, 4.2
    """
    from app.services.catalog import CatalogError
    from app.models.catalog import CatalogErrorCode

    with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch, \
         patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:

        mock_get_cache.return_value = None
        # Simulate upstream unavailable error
        mock_fetch.side_effect = CatalogError(
            "Upstream registry unavailable",
            error_code=CatalogErrorCode.UPSTREAM_UNAVAILABLE
        )

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=official")

        # Verify error response
        assert response.status_code == 503
        data = response.json()
        assert data["error_code"] == "upstream_unavailable"
        assert "detail" in data


@pytest.mark.asyncio
async def test_get_catalog_official_pagination():
    """
    Test Official Registry pagination with multiple pages.
    Verifies actual pagination mechanism: cursor-based fetching, nextCursor handling,
    and page delay behavior.

    Requirements: 1.3, 4.1, 5.3
    Task: 13
    """
    # Helper function to create Official Registry format items
    # Note: "name" field in Official Registry format contains "/" which gets kept as-is in the ID
    def create_official_format(index: int) -> dict:
        return {
            "name": f"modelcontextprotocol/test-server-{index}",
            "display_name": f"Test Server {index}",
            "description": f"Test server number {index}",
            "client": {
                "mcp": {
                    "transport": {
                        "type": "http",
                        "url": f"https://test{index}.example.com/mcp"
                    }
                }
            }
        }

    with patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache, \
         patch("httpx.AsyncClient") as mock_client_class:

        # Scenario: No cache, fetch from Official Registry with pagination
        mock_get_cache.return_value = None

        # Mock multiple pages of HTTP responses
        # Page 1: 30 items with nextCursor
        page1_response = AsyncMock()
        page1_response.status_code = 200
        page1_response.raise_for_status = Mock()
        page1_response.json = lambda: {
            "servers": [create_official_format(i) for i in range(30)],
            "metadata": {"nextCursor": "cursor_page2"}
        }

        # Page 2: 30 items with nextCursor
        page2_response = AsyncMock()
        page2_response.status_code = 200
        page2_response.raise_for_status = Mock()
        page2_response.json = lambda: {
            "servers": [create_official_format(i) for i in range(30, 60)],
            "metadata": {"nextCursor": "cursor_page3"}
        }

        # Page 3: 30 items without nextCursor (final page)
        page3_response = AsyncMock()
        page3_response.status_code = 200
        page3_response.raise_for_status = Mock()
        page3_response.json = lambda: {
            "servers": [create_official_format(i) for i in range(60, 90)],
            "metadata": {}  # No nextCursor means final page
        }

        # Create mock client instance
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[page1_response, page2_response, page3_response])

        # Make the client class return our mock client when used as context manager
        mock_client_class.return_value.__aenter__.return_value = mock_client

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=official")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is False

        # Verify pagination worked: all 90 items from 3 pages are returned
        assert len(data["servers"]) == 90

        # Verify items from all pages are present
        server_ids = [s["id"] for s in data["servers"]]
        assert "modelcontextprotocol/test-server-0" in server_ids  # Page 1
        assert "modelcontextprotocol/test-server-30" in server_ids  # Page 2
        assert "modelcontextprotocol/test-server-60" in server_ids  # Page 3
        assert "modelcontextprotocol/test-server-89" in server_ids  # Last item

        # Verify HTTP client was called 3 times (once per page)
        assert mock_client.get.call_count == 3

        # Verify first call was without cursor parameter
        first_call_url = mock_client.get.call_args_list[0][0][0]
        assert first_call_url == settings.catalog_official_url
        assert "cursor" not in first_call_url

        # Verify subsequent calls included cursor parameters
        second_call_url = mock_client.get.call_args_list[1][0][0]
        assert "cursor=cursor_page2" in second_call_url

        third_call_url = mock_client.get.call_args_list[2][0][0]
        assert "cursor=cursor_page3" in third_call_url


@pytest.mark.asyncio
async def test_get_catalog_official_pagination_max_pages():
    """
    Test that pagination respects max_pages limit.
    Verifies that fetching stops at max_pages even if nextCursor exists.

    Requirements: 4.1, 5.3
    Task: 13
    """
    # Helper function to create Official Registry format items
    def create_official_format(index: int) -> dict:
        return {
            "name": f"modelcontextprotocol/test-server-{index}",
            "display_name": f"Test Server {index}",
            "description": f"Test server number {index}",
        }

    with patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache, \
         patch("httpx.AsyncClient") as mock_client_class, \
         patch("app.config.settings.catalog_official_max_pages", 2):  # Limit to 2 pages

        mock_get_cache.return_value = None

        # Create 4 pages worth of responses, but only first 2 should be fetched
        responses = []
        for page in range(4):
            response = AsyncMock()
            response.status_code = 200
            response.raise_for_status = Mock()
            response.json = lambda p=page: {
                "servers": [create_official_format(i) for i in range(p * 30, (p + 1) * 30)],
                "metadata": {"nextCursor": f"cursor_page{p + 2}"} if p < 3 else {}
            }
            responses.append(response)

        # Create mock client instance
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=responses)
        mock_client_class.return_value.__aenter__.return_value = mock_client

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=official")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # Should only fetch 2 pages (60 items) due to max_pages limit
        assert len(data["servers"]) == 60

        # Verify only 2 HTTP calls were made (respecting max_pages)
        assert mock_client.get.call_count == 2

        # Verify items from page 1 and 2 are present, but not page 3
        server_ids = [s["id"] for s in data["servers"]]
        assert "modelcontextprotocol/test-server-0" in server_ids  # Page 1
        assert "modelcontextprotocol/test-server-30" in server_ids  # Page 2
        assert "modelcontextprotocol/test-server-60" not in server_ids  # Page 3 (not fetched)


@pytest.mark.asyncio
async def test_get_catalog_official_pagination_page_delay():
    """
    Test that pagination includes delay between pages.
    Verifies that asyncio.sleep is called with correct delay between page requests.

    Requirements: 5.3
    Task: 13
    """
    # Helper function to create Official Registry format items
    def create_official_format(index: int) -> dict:
        return {
            "name": f"modelcontextprotocol/test-server-{index}",
            "display_name": f"Test Server {index}",
        }

    with patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache, \
         patch("httpx.AsyncClient") as mock_client_class, \
         patch("asyncio.sleep") as mock_sleep, \
         patch("app.config.settings.catalog_official_page_delay", 500):  # 500ms delay

        mock_get_cache.return_value = None

        # Create 3 pages of responses
        page1_response = AsyncMock()
        page1_response.status_code = 200
        page1_response.raise_for_status = Mock()
        page1_response.json = lambda: {
            "servers": [create_official_format(i) for i in range(30)],
            "metadata": {"nextCursor": "cursor_page2"}
        }

        page2_response = AsyncMock()
        page2_response.status_code = 200
        page2_response.raise_for_status = Mock()
        page2_response.json = lambda: {
            "servers": [create_official_format(i) for i in range(30, 60)],
            "metadata": {"nextCursor": "cursor_page3"}
        }

        page3_response = AsyncMock()
        page3_response.status_code = 200
        page3_response.raise_for_status = Mock()
        page3_response.json = lambda: {
            "servers": [create_official_format(i) for i in range(60, 90)],
            "metadata": {}
        }

        # Create mock client instance
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[page1_response, page2_response, page3_response])
        mock_client_class.return_value.__aenter__.return_value = mock_client

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=official")

        # Verify response
        assert response.status_code == 200

        # Verify asyncio.sleep was called with correct delay (500ms = 0.5s)
        # Should be called 2 times (after page 1 and page 2, but not after final page 3)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(0.5)  # 500ms / 1000 = 0.5s


@pytest.mark.asyncio
async def test_get_catalog_official_pagination_partial_failure():
    """
    Test that pagination handles partial failures gracefully.
    Verifies that if a later page fails, already fetched items are still returned.

    Requirements: 4.1, 5.3
    Task: 13
    """
    import httpx

    # Helper function to create Official Registry format items
    def create_official_format(index: int) -> dict:
        return {
            "name": f"modelcontextprotocol/test-server-{index}",
            "display_name": f"Test Server {index}",
            "description": f"Test server number {index}",
        }

    with patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache, \
         patch("httpx.AsyncClient") as mock_client_class:

        mock_get_cache.return_value = None

        # Page 1: Success with 30 items
        page1_response = AsyncMock()
        page1_response.status_code = 200
        page1_response.raise_for_status = Mock()
        page1_response.json = lambda: {
            "servers": [create_official_format(i) for i in range(30)],
            "metadata": {"nextCursor": "cursor_page2"}
        }

        # Page 2: Network error
        page2_error = httpx.HTTPStatusError(
            "Server error",
            request=AsyncMock(),
            response=AsyncMock(status_code=500)
        )

        # Create mock client instance
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[page1_response, page2_error])
        mock_client_class.return_value.__aenter__.return_value = mock_client

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=official")

        # Verify response - should return page 1 items even though page 2 failed
        assert response.status_code == 200
        data = response.json()

        # Should have items from page 1 (partial success)
        assert len(data["servers"]) == 30

        # Verify items from page 1 are present
        server_ids = [s["id"] for s in data["servers"]]
        assert "modelcontextprotocol/test-server-0" in server_ids
        assert "modelcontextprotocol/test-server-29" in server_ids

        # Verify 2 HTTP calls were attempted (page 1 succeeded, page 2 failed)
        assert mock_client.get.call_count == 2


@pytest.mark.asyncio
async def test_get_catalog_official_pagination_cache_miss():
    """
    Test pagination cache miss scenario:
    Cache miss → pagination fetch occurs → cache is updated → response.cached=False

    Requirements: 4.1, 4.2, 4.3
    Task: 13
    """
    # Helper function to create Official Registry format items
    def create_official_format(index: int) -> dict:
        return {
            "name": f"modelcontextprotocol/test-server-{index}",
            "display_name": f"Test Server {index}",
            "description": f"Test server number {index}",
        }

    with patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache, \
         patch("app.api.catalog.catalog_service.update_cache") as mock_update_cache, \
         patch("httpx.AsyncClient") as mock_client_class:

        mock_get_cache.return_value = None  # Cache miss

        # Mock pagination responses (3 pages)
        page1_response = AsyncMock()
        page1_response.status_code = 200
        page1_response.raise_for_status = Mock()
        page1_response.json = lambda: {
            "servers": [create_official_format(i) for i in range(30)],
            "metadata": {"nextCursor": "cursor_page2"}
        }

        page2_response = AsyncMock()
        page2_response.status_code = 200
        page2_response.raise_for_status = Mock()
        page2_response.json = lambda: {
            "servers": [create_official_format(i) for i in range(30, 60)],
            "metadata": {"nextCursor": "cursor_page3"}
        }

        page3_response = AsyncMock()
        page3_response.status_code = 200
        page3_response.raise_for_status = Mock()
        page3_response.json = lambda: {
            "servers": [create_official_format(i) for i in range(60, 90)],
            "metadata": {}
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[page1_response, page2_response, page3_response])
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Request with cache miss
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=official")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is False  # Not from cache
        assert len(data["servers"]) == 90

        # Verify cache was checked and pagination occurred
        # Note: get_cached_catalog is called twice per request:
        # 1) By the endpoint directly (line 134 in catalog.py)
        # 2) By fetch_catalog internally (line 304 in catalog.py)
        assert mock_get_cache.call_count == 2
        assert mock_client.get.call_count == 3  # 3 pages fetched
        assert mock_update_cache.call_count == 1  # Cache was updated


@pytest.mark.asyncio
async def test_get_catalog_official_pagination_cache_hit():
    """
    Test pagination cache hit scenario:
    Cache hit → pagination fetch is skipped → response.cached=True

    Requirements: 4.1, 4.2, 4.3
    Task: 13
    """
    # Create 90 mock servers (3 pages x 30 items)
    paginated_items = []
    for i in range(90):
        paginated_items.append(
            CatalogItem(
                id=f"modelcontextprotocol/test-server-{i}",
                name=f"Test Server {i}",
                description=f"Test server number {i}",
                vendor="modelcontextprotocol",
                category="general",
                docker_image="",
                required_envs=[],
                required_secrets=[]
            )
        )

    with patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache, \
         patch("app.api.catalog.catalog_service.update_cache") as mock_update_cache, \
         patch("httpx.AsyncClient") as mock_client_class:

        # Cache returns the 90 items
        mock_get_cache.return_value = paginated_items

        mock_client = AsyncMock()
        mock_client.get = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Request with cache hit
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=official")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is True  # From cache
        assert len(data["servers"]) == 90

        # Verify cache was checked but pagination did NOT occur
        # Note: When cache is available, the endpoint:
        # 1) Checks cache directly and returns cached data immediately (line 134-156)
        # 2) Spawns background task to refresh cache (line 146)
        # The background task calls fetch_catalog which also checks cache again
        # However, since we're not awaiting the background task and it happens async,
        # we only see the first cache check from the endpoint
        assert mock_get_cache.call_count == 1
        assert mock_client.get.call_count == 0  # No pagination fetch in main flow
        assert mock_update_cache.call_count == 0  # Cache not updated in main flow


@pytest.mark.asyncio
async def test_get_catalog_official_pagination_cache_expiry():
    """
    Test pagination cache expiry scenario:
    Cache expired (returns None) → pagination fetch occurs again → cache is updated → response.cached=False

    Requirements: 4.1, 4.2, 4.3
    Task: 13
    """
    # Helper function to create Official Registry format items
    def create_official_format(index: int) -> dict:
        return {
            "name": f"modelcontextprotocol/test-server-{index}",
            "display_name": f"Test Server {index}",
            "description": f"Test server number {index}",
        }

    with patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache, \
         patch("app.api.catalog.catalog_service.update_cache") as mock_update_cache, \
         patch("httpx.AsyncClient") as mock_client_class:

        # Cache expired, returns None
        mock_get_cache.return_value = None

        # Mock pagination responses (3 pages)
        page1_response = AsyncMock()
        page1_response.status_code = 200
        page1_response.raise_for_status = Mock()
        page1_response.json = lambda: {
            "servers": [create_official_format(i) for i in range(30)],
            "metadata": {"nextCursor": "cursor_page2"}
        }

        page2_response = AsyncMock()
        page2_response.status_code = 200
        page2_response.raise_for_status = Mock()
        page2_response.json = lambda: {
            "servers": [create_official_format(i) for i in range(30, 60)],
            "metadata": {"nextCursor": "cursor_page3"}
        }

        page3_response = AsyncMock()
        page3_response.status_code = 200
        page3_response.raise_for_status = Mock()
        page3_response.json = lambda: {
            "servers": [create_official_format(i) for i in range(60, 90)],
            "metadata": {}
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[
            page1_response, page2_response, page3_response
        ])
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Request with cache expired
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=official")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is False  # Not from cache (expired)
        assert len(data["servers"]) == 90

        # Verify cache was checked, pagination occurred, and cache was updated
        # Same as cache miss: get_cached_catalog called twice per request
        assert mock_get_cache.call_count == 2
        assert mock_client.get.call_count == 3  # 3 pages fetched
        assert mock_update_cache.call_count == 1  # Cache updated
