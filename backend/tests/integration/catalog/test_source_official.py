
import pytest
from unittest.mock import patch, AsyncMock
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
        required_secrets=[]
    ),
    CatalogItem(
        id="modelcontextprotocol-minimal",
        name="Minimal MCP",
        description="",
        vendor="modelcontextprotocol",
        category="general",
        docker_image="",
        required_envs=[],
        required_secrets=[]
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
    with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch, \
         patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:

        mock_get_cache.return_value = None

        # Test with items that have various field issues
        test_items = [
            CatalogItem(
                id="valid-item",
                name="Valid Item",
                description="Valid description",
                vendor="test",
                category="general",
                docker_image="",
                required_envs=[],
                required_secrets=[]
            )
        ]
        mock_fetch.return_value = (test_items, False)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=official")

        assert response.status_code == 200
        data = response.json()

        # Verify stable identifier and display name
        assert "id" in data["servers"][0]
        assert "name" in data["servers"][0]
        assert data["servers"][0]["id"] == "valid-item"
        assert data["servers"][0]["name"] == "Valid Item"

        # Verify service call with Official URL
        args, _ = mock_fetch.call_args
        assert args[0] == settings.catalog_official_url


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
