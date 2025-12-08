"""Tests for Catalog Service."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, Response

from app.models.catalog import CatalogItem
from app.services.catalog import CatalogError, CatalogService


@pytest.fixture
def catalog_service():
    """Create a fresh CatalogService instance for each test."""
    return CatalogService()


@pytest.fixture
def sample_catalog_data():
    """Sample catalog data (Registry format) for testing."""
    return [
        {
            "name": "fetch",
            "description": "Web fetch tool",
            "vendor": "Docker Inc.",
            "image": "docker/mcp-fetch:latest",
                "required_envs": ["API_KEY", "PORT"]
        },
        {
            "name": "filesystem",
            "description": "File system access",
            "vendor": "Docker Inc.",
            "image": "docker/mcp-filesystem:latest",
            "required_envs": []
        }
    ]


@pytest.fixture
def sample_catalog_items(sample_catalog_data):
    """Sample CatalogItem objects for testing."""
    items = []
    for item in sample_catalog_data:
        items.append(CatalogItem(
            id=item["name"],
            name=item["name"],
            description=item["description"],
            vendor=item["vendor"],
            category="general",
            docker_image=item["image"],
            default_env={},
            required_envs=item["required_envs"],
            required_secrets=["API_KEY"] if "API_KEY" in item["required_envs"] else []
        ))
    return items


class TestCatalogService:
    """Test suite for CatalogService."""

    @pytest.mark.asyncio
    async def test_search_by_keyword(self, catalog_service, sample_catalog_items):
        """Test keyword search in catalog."""
        # Search for "fetch" - should match first item
        results = await catalog_service.search_catalog(
            sample_catalog_items,
            query="fetch"
        )
        assert len(results) == 1
        assert results[0].name == "fetch"

    @pytest.mark.asyncio
    async def test_search_by_category(self, catalog_service, sample_catalog_items):
        """Test category filtering."""
        # Filter by "general" category
        results = await catalog_service.search_catalog(
            sample_catalog_items,
            category="general"
        )
        assert len(results) == 2
        assert all(item.category == "general" for item in results)

    @pytest.mark.asyncio
    async def test_search_combined_filters(self, catalog_service, sample_catalog_items):
        """Test combined keyword and category filtering."""
        # Search for "fetch" in "general" category
        results = await catalog_service.search_catalog(
            sample_catalog_items,
            query="fetch",
            category="general"
        )
        assert len(results) == 1
        assert results[0].category == "general"
        assert "fetch" in results[0].name.lower()

    @pytest.mark.asyncio
    async def test_search_no_results(self, catalog_service, sample_catalog_items):
        """Test search with no matching results."""
        results = await catalog_service.search_catalog(
            sample_catalog_items,
            query="nonexistent"
        )
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("app.services.catalog.httpx.AsyncClient")
    async def test_fetch_from_url_required_envs_and_secrets(self, mock_client, catalog_service, sample_catalog_data):
        """Registry required_envs should map to required_envs and secrets heuristic."""
        mock_response = AsyncMock()
        mock_response.json.return_value = sample_catalog_data
        mock_response.raise_for_status.return_value = None

        client_instance = AsyncMock()
        client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = client_instance

        items = await catalog_service._fetch_from_url("http://example.com/catalog.json")

        assert items[0].required_envs == ["API_KEY", "PORT"]
        assert "API_KEY" in items[0].required_secrets
        assert "PORT" not in items[0].required_secrets

    @pytest.mark.asyncio
    async def test_search_empty_query(self, catalog_service, sample_catalog_items):
        """Test search with empty query returns all items."""
        results = await catalog_service.search_catalog(
            sample_catalog_items,
            query=""
        )
        assert len(results) == len(sample_catalog_items)

    @pytest.mark.asyncio
    async def test_cache_operations(self, catalog_service, sample_catalog_items):
        """Test cache set and get operations."""
        source_url = "https://example.com/catalog.json"
        
        # Initially no cache
        cached = await catalog_service.get_cached_catalog(source_url)
        assert cached is None
        
        # Set cache
        await catalog_service.update_cache(source_url, sample_catalog_items)
        
        # Should now be cached
        cached = await catalog_service.get_cached_catalog(source_url)
        assert cached is not None
        assert len(cached) == len(sample_catalog_items)
        assert cached[0].id == sample_catalog_items[0].id

    @pytest.mark.asyncio
    async def test_cache_expiry(self, catalog_service, sample_catalog_items):
        """Test that expired cache is not returned."""
        source_url = "https://example.com/catalog.json"
        
        # Set cache with very short TTL
        catalog_service._cache_ttl = timedelta(seconds=0)
        await catalog_service.update_cache(source_url, sample_catalog_items)
        
        # Cache should be expired immediately
        cached = await catalog_service.get_cached_catalog(source_url)
        assert cached is None

    @pytest.mark.asyncio
    async def test_clear_cache_specific(self, catalog_service, sample_catalog_items):
        """Test clearing cache for specific URL."""
        url1 = "https://example.com/catalog1.json"
        url2 = "https://example.com/catalog2.json"
        
        # Set cache for both URLs
        await catalog_service.update_cache(url1, sample_catalog_items)
        await catalog_service.update_cache(url2, sample_catalog_items)
        
        # Clear cache for url1
        catalog_service.clear_cache(url1)
        
        # url1 should be cleared, url2 should remain
        assert await catalog_service.get_cached_catalog(url1) is None
        assert await catalog_service.get_cached_catalog(url2) is not None

    @pytest.mark.asyncio
    async def test_clear_cache_all(self, catalog_service, sample_catalog_items):
        """Test clearing all cache."""
        url1 = "https://example.com/catalog1.json"
        url2 = "https://example.com/catalog2.json"
        
        # Set cache for both URLs
        await catalog_service.update_cache(url1, sample_catalog_items)
        await catalog_service.update_cache(url2, sample_catalog_items)
        
        # Clear all cache
        catalog_service.clear_cache()
        
        # Both should be cleared
        assert await catalog_service.get_cached_catalog(url1) is None
        assert await catalog_service.get_cached_catalog(url2) is None

    @pytest.mark.asyncio
    async def test_cleanup_expired_cache(self, catalog_service, sample_catalog_items):
        """Test cleanup of expired cache entries."""
        url1 = "https://example.com/catalog1.json"
        url2 = "https://example.com/catalog2.json"
        
        # Set cache for url1 with short TTL
        catalog_service._cache_ttl = timedelta(seconds=0)
        await catalog_service.update_cache(url1, sample_catalog_items)
        
        # Set cache for url2 with long TTL
        catalog_service._cache_ttl = timedelta(hours=1)
        await catalog_service.update_cache(url2, sample_catalog_items)
        
        # Cleanup expired entries
        removed = await catalog_service.cleanup_expired_cache()
        
        # Should have removed url1 only
        assert removed == 1
        assert await catalog_service.get_cached_catalog(url1) is None
        assert await catalog_service.get_cached_catalog(url2) is not None


class TestCatalogModels:
    """Test suite for Catalog models."""

    def test_catalog_item_creation(self):
        """Test creating a CatalogItem."""
        item = CatalogItem(
            id="test-1",
            name="Test Server",
            description="A test server",
            vendor="Test Vendor",
            category="utilities",
            docker_image="test/server:latest",
            default_env={"PORT": "8080"},
            required_envs=["PORT", "API_KEY"],
            required_secrets=["API_KEY"]
        )
        
        assert item.id == "test-1"
        assert item.name == "Test Server"
        assert item.category == "utilities"
        assert item.default_env["PORT"] == "8080"
        assert "PORT" in item.required_envs
        assert "API_KEY" in item.required_secrets

    def test_catalog_item_defaults(self):
        """Test CatalogItem with default values."""
        item = CatalogItem(
            id="test-1",
            name="Test Server",
            description="A test server",
            category="utilities",
            docker_image="test/server:latest"
        )
        
        assert item.vendor == ""
        assert item.required_envs == []
        assert item.default_env == {}
        assert item.required_secrets == []



class TestCatalogFetch:
    """Test suite for catalog fetching functionality."""

    @pytest.mark.asyncio
    async def test_fetch_catalog_success(self, catalog_service, sample_catalog_data, monkeypatch):
        """Test successful catalog fetch from URL."""
        from unittest.mock import AsyncMock, MagicMock
        
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.json.return_value = sample_catalog_data
        mock_response.raise_for_status = MagicMock()
        
        mock_get = AsyncMock(return_value=mock_response)
        
        class MockAsyncClient:
            def __init__(self, *args, **kwargs):
                pass
            
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, *args):
                pass
            
            async def get(self, *args, **kwargs):
                return await mock_get(*args, **kwargs)
        
        import httpx
        monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
        
        # Fetch catalog
        source_url = "https://example.com/catalog.json"
        items, is_cached = await catalog_service.fetch_catalog(source_url)
        
        # Verify results
        assert len(items) == 2
        assert is_cached is False
        assert items[0].id == "fetch"
        assert items[1].id == "filesystem"
        
        # Verify cache was updated
        cached = await catalog_service.get_cached_catalog(source_url)
        assert cached is not None
        assert len(cached) == 2

    @pytest.mark.asyncio
    async def test_fetch_catalog_fallback_to_cache(self, catalog_service, sample_catalog_items, monkeypatch):
        """Test fallback to cache when fetch fails."""
        import httpx
        
        # Pre-populate cache
        source_url = "https://example.com/catalog.json"
        await catalog_service.update_cache(source_url, sample_catalog_items)
        
        # Mock httpx to raise an error
        class MockAsyncClient:
            def __init__(self, *args, **kwargs):
                pass
            
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, *args):
                pass
            
            async def get(self, *args, **kwargs):
                raise httpx.RequestError("Network error")
        
        monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
        
        # Fetch should fall back to cache
        items, is_cached = await catalog_service.fetch_catalog(source_url)
        
        # Should return cached data
        assert len(items) == len(sample_catalog_items)
        assert is_cached is True
        assert items[0].id == sample_catalog_items[0].id

    @pytest.mark.asyncio
    async def test_fetch_catalog_no_cache_fails(self, catalog_service, monkeypatch):
        """Test that fetch fails when no cache is available."""
        import httpx
        
        # Mock httpx to raise an error
        class MockAsyncClient:
            def __init__(self, *args, **kwargs):
                pass
            
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, *args):
                pass
            
            async def get(self, *args, **kwargs):
                raise httpx.RequestError("Network error")
        
        monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
        
        # Fetch should fail with no cache
        source_url = "https://example.com/catalog.json"
        with pytest.raises(CatalogError) as exc_info:
            await catalog_service.fetch_catalog(source_url)
        
        assert "no cached data available" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_fetch_catalog_invalid_json(self, catalog_service, monkeypatch):
        """Test handling of invalid JSON response."""
        from unittest.mock import MagicMock, AsyncMock
        import httpx
        
        # Mock httpx with invalid JSON
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.raise_for_status = MagicMock()
        
        mock_get = AsyncMock(return_value=mock_response)
        
        class MockAsyncClient:
            def __init__(self, *args, **kwargs):
                pass
            
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, *args):
                pass
            
            async def get(self, *args, **kwargs):
                return await mock_get(*args, **kwargs)
        
        monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
        
        # Fetch should fail
        source_url = "https://example.com/catalog.json"
        with pytest.raises(CatalogError) as exc_info:
            await catalog_service.fetch_catalog(source_url)
        
        assert "no cached data available" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_fetch_catalog_http_error(self, catalog_service, monkeypatch):
        """Test handling of HTTP errors."""
        from unittest.mock import MagicMock
        import httpx
        
        # Mock httpx with HTTP error
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        class MockAsyncClient:
            def __init__(self, *args, **kwargs):
                pass
            
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, *args):
                pass
            
            async def get(self, *args, **kwargs):
                raise httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)
        
        monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
        
        # Fetch should fail
        source_url = "https://example.com/catalog.json"
        with pytest.raises(CatalogError) as exc_info:
            await catalog_service.fetch_catalog(source_url)
        
        assert "no cached data available" in str(exc_info.value).lower()
