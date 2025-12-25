
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.main import app
from app.config import settings
from app.models.catalog import CatalogItem
from httpx import AsyncClient

# Sample CatalogItem matching the expected result of source=docker
DOCKER_CATALOG_ITEMS = [
    CatalogItem(
        id="mcp-server-test",
        name="test-server",
        description="A test server",
        vendor="TestVendor",
        category="general",
        docker_image="test-image",
        required_envs=[],
        required_secrets=[]
    )
]

@pytest.mark.asyncio
async def test_get_catalog_docker_source():
    """
    Test E2E flow for source=docker.
    Mocks the catalog_service.fetch_catalog to return predefined items.
    """
    # Patch the global catalog_service instance in app.api.catalog
    with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch, \
         patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:
        
        # Scenario: No cache available, fetch succeeds
        mock_get_cache.return_value = None
        mock_fetch.return_value = (DOCKER_CATALOG_ITEMS, False)
        
        # Using standard app argument as in other tests
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=docker")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is False
        assert len(data["servers"]) == 1
        assert data["servers"][0]["id"] == "mcp-server-test"
        
        # Verify service call
        mock_fetch.assert_called_once()
        # Ensure it was called with docker URL
        args, _ = mock_fetch.call_args
        assert args[0] == settings.catalog_docker_url

@pytest.mark.asyncio
async def test_get_catalog_default_source_fallback():
    """
    Test that omitting source parameter defaults to docker source.
    """
    with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch, \
         patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:
        
        mock_get_cache.return_value = None
        mock_fetch.return_value = (DOCKER_CATALOG_ITEMS, False)
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog")
            
        assert response.status_code == 200
        data = response.json()
        assert len(data["servers"]) == 1
        
        # Verify default behavior used Docker URL
        args, _ = mock_fetch.call_args
        assert args[0] == settings.catalog_docker_url

@pytest.mark.asyncio
async def test_get_catalog_cached():
    """
    Test verify correct behavior when cache exists.
    Expected: returns cached data with cached=True.
    """
    with patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:

        # Scenario: Cache available
        mock_get_cache.return_value = DOCKER_CATALOG_ITEMS

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=docker")

        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is True
        assert len(data["servers"]) == 1

        # Verify get_cached_catalog was called
        mock_get_cache.assert_called_once()
