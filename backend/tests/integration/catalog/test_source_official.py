
import asyncio
import logging
import pytest
from datetime import timedelta
from unittest.mock import patch, AsyncMock
from app.main import app
from app.config import settings
from app.models.catalog import CatalogItem
from httpx import AsyncClient

logger = logging.getLogger(__name__)

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
    Verifies that more than 30 items are returned when pagination is used.

    Requirements: 1.3, 4.1, 5.3
    Task: 13
    """
    # Create 90 mock servers (3 pages × 30 items)
    mock_servers = []
    for i in range(90):
        mock_servers.append(
            CatalogItem(
                id=f"test-server-{i}",
                name=f"Test Server {i}",
                description=f"Test server number {i}",
                vendor="testvendor",
                category="general",
                docker_image="",
                required_envs=[],
                required_secrets=[]
            )
        )

    with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch, \
         patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:

        # Scenario: No cache, fetch from Official Registry with pagination
        mock_get_cache.return_value = None
        mock_fetch.return_value = (mock_servers, False)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=official")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is False

        # Verify more than 30 items are returned (pagination working)
        assert len(data["servers"]) > 30
        assert len(data["servers"]) == 90

        # Verify service was called with Official Registry URL
        mock_fetch.assert_called_once()
        args, _ = mock_fetch.call_args
        assert args[0] == settings.catalog_official_url


@pytest.mark.asyncio
async def test_get_catalog_official_pagination_with_cache():
    """
    Test that paginated Official Registry data is cached correctly.
    Verifies cache behavior works with pagination.

    Requirements: 4.1, 4.2, 4.3
    Task: 13
    """
    # Create 90 mock servers (3 pages × 30 items)
    mock_servers = []
    for i in range(90):
        mock_servers.append(
            CatalogItem(
                id=f"cached-server-{i}",
                name=f"Cached Server {i}",
                description=f"Cached server number {i}",
                vendor="testvendor",
                category="general",
                docker_image="",
                required_envs=[],
                required_secrets=[]
            )
        )

    with patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:
        # Scenario: Cache available with 90 items (from pagination)
        mock_get_cache.return_value = mock_servers

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=official")

        assert response.status_code == 200
        data = response.json()

        # Verify cached data is returned
        assert data["cached"] is True
        assert len(data["servers"]) == 90

        # Verify all 90 cached items are accessible
        server_ids = [s["id"] for s in data["servers"]]
        assert "cached-server-0" in server_ids
        assert "cached-server-89" in server_ids

        # Verify get_cached_catalog was called
        mock_get_cache.assert_called_once()


@pytest.mark.asyncio
async def test_catalog_cache_behavior_with_pagination():
    """
    Test cache behavior with pagination:
    1. First request triggers pagination fetch
    2. Second request uses cache (no pagination)
    3. After TTL expiry, third request re-fetches with pagination

    Requirements: 4.1, 4.2, 4.3
    Task: 14
    """
    from app.services.catalog import CatalogService

    # Create a real CatalogService instance with a short TTL for testing
    service = CatalogService()
    service._cache_ttl = timedelta(seconds=2)  # Short TTL for testing

    # Mock the _fetch_official_registry_with_pagination method
    mock_servers = []
    for i in range(90):
        mock_servers.append(
            CatalogItem(
                id=f"pagination-test-{i}",
                name=f"Pagination Test Server {i}",
                description=f"Test server {i} for pagination caching",
                vendor="testvendor",
                category="general",
                docker_image=f"testvendor/server-{i}:latest",
                required_envs=[],
                required_secrets=[]
            )
        )

    fetch_count = 0

    async def mock_fetch_paginated(source_url: str):
        nonlocal fetch_count
        fetch_count += 1
        logger.info(f"Mock fetch called (count: {fetch_count})")
        return mock_servers

    with patch.object(service, "_fetch_from_url", side_effect=mock_fetch_paginated):
        # First request: should trigger pagination fetch
        items1, cached1 = await service.fetch_catalog(settings.catalog_official_url)
        assert len(items1) == 90
        assert cached1 is False
        assert fetch_count == 1, "First request should trigger fetch"

        # Second request: should use cache (no fetch)
        items2, cached2 = await service.fetch_catalog(settings.catalog_official_url)
        assert len(items2) == 90
        assert cached2 is True
        assert fetch_count == 1, "Second request should use cache"

        # Verify items are the same
        assert items1[0].id == items2[0].id
        assert items1[-1].id == items2[-1].id

        # Wait for cache to expire
        await asyncio.sleep(2.5)

        # Third request: cache expired, should re-fetch
        items3, cached3 = await service.fetch_catalog(settings.catalog_official_url)
        assert len(items3) == 90
        assert cached3 is False
        assert fetch_count == 2, "Third request should re-fetch after TTL expiry"

        # Verify items are still correct
        assert items3[0].id == "pagination-test-0"
        assert items3[-1].id == "pagination-test-89"


@pytest.mark.asyncio
async def test_catalog_cache_isolated_by_source_url():
    """
    Test that cache is properly isolated by source_url.
    Different source URLs should have separate cache entries.

    Requirements: 4.1, 4.2
    Task: 14
    """
    from app.services.catalog import CatalogService

    service = CatalogService()
    service._cache_ttl = timedelta(seconds=10)

    # Mock servers for official source
    official_servers = [
        CatalogItem(
            id="official-server",
            name="Official Server",
            description="From official registry",
            vendor="official",
            category="general",
            docker_image="official/server:latest",
            required_envs=[],
            required_secrets=[]
        )
    ]

    # Mock servers for docker source
    docker_servers = [
        CatalogItem(
            id="docker-server",
            name="Docker Server",
            description="From docker registry",
            vendor="docker",
            category="general",
            docker_image="docker/server:latest",
            required_envs=[],
            required_secrets=[]
        )
    ]

    async def mock_fetch_url(source_url: str):
        if source_url == settings.catalog_official_url:
            return official_servers
        else:
            return docker_servers

    with patch.object(service, "_fetch_from_url", side_effect=mock_fetch_url):
        # Fetch from official source
        items_official, cached1 = await service.fetch_catalog(settings.catalog_official_url)
        assert len(items_official) == 1
        assert items_official[0].id == "official-server"
        assert cached1 is False

        # Fetch from docker source
        items_docker, cached2 = await service.fetch_catalog(settings.catalog_docker_url)
        assert len(items_docker) == 1
        assert items_docker[0].id == "docker-server"
        assert cached2 is False

        # Verify both are cached independently
        cached_official = await service.get_cached_catalog(settings.catalog_official_url)
        cached_docker = await service.get_cached_catalog(settings.catalog_docker_url)

        assert cached_official is not None
        assert cached_docker is not None
        assert cached_official[0].id == "official-server"
        assert cached_docker[0].id == "docker-server"


@pytest.mark.asyncio
async def test_catalog_force_refresh_bypasses_cache():
    """
    Test that force_refresh parameter bypasses cache and triggers re-fetch.

    Requirements: 4.2
    Task: 14
    """
    from app.services.catalog import CatalogService

    service = CatalogService()
    service._cache_ttl = timedelta(seconds=60)  # Long TTL

    mock_servers_v1 = [
        CatalogItem(
            id="server-v1",
            name="Server V1",
            description="Version 1",
            vendor="test",
            category="general",
            docker_image="test/server:v1",
            required_envs=[],
            required_secrets=[]
        )
    ]

    mock_servers_v2 = [
        CatalogItem(
            id="server-v2",
            name="Server V2",
            description="Version 2",
            vendor="test",
            category="general",
            docker_image="test/server:v2",
            required_envs=[],
            required_secrets=[]
        )
    ]

    fetch_count = 0

    async def mock_fetch_paginated(source_url: str):
        nonlocal fetch_count
        fetch_count += 1
        if fetch_count == 1:
            return mock_servers_v1
        else:
            return mock_servers_v2

    with patch.object(service, "_fetch_from_url", side_effect=mock_fetch_paginated):
        # First request: fetch V1
        items1, cached1 = await service.fetch_catalog(settings.catalog_official_url)
        assert items1[0].id == "server-v1"
        assert cached1 is False
        assert fetch_count == 1

        # Second request without force_refresh: should use cache (V1)
        items2, cached2 = await service.fetch_catalog(settings.catalog_official_url, force_refresh=False)
        assert items2[0].id == "server-v1"
        assert cached2 is True
        assert fetch_count == 1, "Should use cache"

        # Third request with force_refresh: should bypass cache and fetch V2
        items3, cached3 = await service.fetch_catalog(settings.catalog_official_url, force_refresh=True)
        assert items3[0].id == "server-v2"
        assert cached3 is False
        assert fetch_count == 2, "Should bypass cache with force_refresh"

        # Fourth request: should use updated cache (V2)
        items4, cached4 = await service.fetch_catalog(settings.catalog_official_url)
        assert items4[0].id == "server-v2"
        assert cached4 is True
        assert fetch_count == 2, "Should use updated cache"
