"""
Integration tests for catalog API source parameter:
- Default source behavior (omitted parameter)
- Invalid source values
- Backward compatibility with existing clients

Requirements: 2.2, 2.5, 5.2, 6.1, 6.2
"""

import pytest
from unittest.mock import patch
from app.main import app
from app.config import settings
from app.models.catalog import CatalogItem
from httpx import AsyncClient


# Sample CatalogItem for testing
SAMPLE_CATALOG_ITEMS = [
    CatalogItem(
        id="test-server",
        name="Test Server",
        description="A test server for integration tests",
        vendor="TestVendor",
        category="general",
        docker_image="test-image:latest",
        required_envs=[],
        required_secrets=[]
    )
]


@pytest.mark.asyncio
async def test_get_catalog_source_omitted_defaults_to_docker():
    """
    Test that when source parameter is omitted, it defaults to Docker source.
    This is critical for backward compatibility.

    Requirements: 2.2, 6.1, 6.2
    """
    with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch, \
         patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:

        mock_get_cache.return_value = None
        mock_fetch.return_value = (SAMPLE_CATALOG_ITEMS, False)

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Request without source parameter
            response = await client.get("/api/catalog")

        # Verify successful response
        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is False
        assert len(data["servers"]) == 1
        assert data["servers"][0]["id"] == "test-server"

        # Verify fetch_catalog was called with Docker URL (default behavior)
        mock_fetch.assert_called_once()
        args, _ = mock_fetch.call_args
        assert args[0] == settings.catalog_docker_url


@pytest.mark.asyncio
async def test_get_catalog_source_empty_string_returns_400():
    """
    Test that when source parameter is empty string, it returns 400.
    This covers edge case of ?source= with no value.
    Empty string is treated as an invalid source value by FastAPI/Pydantic.

    Requirements: 2.5, 5.2
    """
    with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch:

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Request with empty source parameter
            response = await client.get("/api/catalog?source=")

        # Empty string is invalid, should return 400
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "invalid_source"

        # Verify no upstream request was made
        mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_get_catalog_invalid_source_returns_400():
    """
    Test that invalid source values return 400 Bad Request with structured error.
    Verifies that no upstream request is made.

    Requirements: 2.5, 5.2
    """
    invalid_sources = [
        "invalid",
        "unknown",
        "custom-registry",
        "http://malicious.example.com",
        "../path/traversal",
        "docker-typo",
        "Docker",  # Case sensitive
        "OFFICIAL",  # Case sensitive
    ]

    for invalid_source in invalid_sources:
        with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch, \
             patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:

            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get(f"/api/catalog?source={invalid_source}")

            # Verify 400 Bad Request response
            assert response.status_code == 400, f"Expected 400 for source={invalid_source}"
            data = response.json()

            # Verify structured error response
            assert "error_code" in data, f"Missing error_code for source={invalid_source}"
            assert data["error_code"] == "invalid_source", \
                f"Expected error_code='invalid_source' for source={invalid_source}"
            assert "detail" in data, f"Missing detail for source={invalid_source}"

            # Verify no upstream request was made
            mock_fetch.assert_not_called()
            mock_get_cache.assert_not_called()


@pytest.mark.asyncio
async def test_get_catalog_invalid_source_no_upstream_request():
    """
    Test that invalid source values do not trigger any outbound request to upstream.
    This is a security requirement to prevent SSRF.

    Requirements: 5.2
    """
    with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch, \
         patch("app.api.catalog.catalog_service._fetch_from_url") as mock_fetch_url:

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=http://evil.com")

        # Verify no service calls were made
        assert response.status_code == 400
        mock_fetch.assert_not_called()
        mock_fetch_url.assert_not_called()


@pytest.mark.asyncio
async def test_get_catalog_backward_compatibility_existing_clients():
    """
    Test backward compatibility for existing clients that don't specify source.
    Verifies that response schema is compatible with pre-feature schema.

    Requirements: 6.1, 6.2
    """
    with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch, \
         patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:

        mock_get_cache.return_value = None
        mock_fetch.return_value = (SAMPLE_CATALOG_ITEMS, False)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog")

        # Verify response structure is compatible
        assert response.status_code == 200
        data = response.json()

        # Verify required fields exist (pre-feature schema)
        assert "servers" in data
        assert "cached" in data
        assert isinstance(data["servers"], list)
        assert isinstance(data["cached"], bool)

        # Verify server item structure
        if len(data["servers"]) > 0:
            server = data["servers"][0]
            required_fields = ["id", "name", "description", "vendor", "category"]
            for field in required_fields:
                assert field in server, f"Missing required field: {field}"


@pytest.mark.asyncio
async def test_search_catalog_source_omitted_defaults_to_docker():
    """
    Test that search endpoint also defaults to Docker when source is omitted.
    Verifies consistency between /api/catalog and /api/catalog/search endpoints.

    Requirements: 2.2, 6.1
    """
    with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch, \
         patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:

        mock_get_cache.return_value = None
        mock_fetch.return_value = (SAMPLE_CATALOG_ITEMS, False)

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Search without source parameter
            response = await client.get("/api/catalog/search?q=test")

        # Verify successful response
        assert response.status_code == 200

        # Verify fetch_catalog was called with Docker URL
        mock_fetch.assert_called_once()
        args, _ = mock_fetch.call_args
        assert args[0] == settings.catalog_docker_url


@pytest.mark.asyncio
async def test_search_catalog_invalid_source_returns_400():
    """
    Test that search endpoint returns 400 for invalid source values.
    Verifies consistency with main catalog endpoint.

    Requirements: 2.5, 5.2
    """
    with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch:
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog/search?source=invalid&q=test")

        # Verify 400 Bad Request with structured error
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "invalid_source"

        # Verify no upstream request was made
        mock_fetch.assert_not_called()
