
import asyncio
import json
from typing import List, Dict
from datetime import datetime, timedelta
import pytest
from hypothesis import given, strategies as st, settings as hyp_settings
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.catalog import CatalogItem, Catalog
from app.services.catalog import CatalogService, CatalogError

# Strategies
def catalog_items():
    return st.builds(
        CatalogItem,
        id=st.text(min_size=1),
        name=st.text(min_size=1),
        description=st.text(),
        category=st.text(min_size=1),
        docker_image=st.text(min_size=1),
        default_env=st.dictionaries(st.text(min_size=1), st.text()),
        required_secrets=st.lists(st.text(min_size=1))
    )

def catalog_lists():
    return st.lists(catalog_items(), min_size=1)

@pytest.fixture
def catalog_service():
    return CatalogService()

@pytest.mark.asyncio
class TestCatalogProperties:

    # Task 5.1: Catalog data fetching property test (Property 9)
    @given(catalog_lists())
    @hyp_settings(max_examples=50)
    async def test_catalog_data_fetching(self, items: List[CatalogItem]):
        """
        **Feature: docker-mcp-gateway-console, Property 9: Catalog data fetching**
        
        For any valid Catalog data source, the system should retrieve the list of MCP servers,
        and each item should contain the required fields.
        """
        service = CatalogService()
        
        # Construct a valid Catalog object from generated items
        catalog_data = Catalog(version="1.0", servers=items)
        json_response = catalog_data.model_dump()

        # Mock the HTTP client
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = json_response
            mock_response.raise_for_status = MagicMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            MockClient.return_value = mock_instance

            fetched_items, is_cached = await service.fetch_catalog("http://test.url")
            
            assert len(fetched_items) == len(items)
            assert is_cached is False
            
            for i, item in enumerate(fetched_items):
                assert item.id == items[i].id
                assert item.name == items[i].name
                assert item.docker_image == items[i].docker_image

    # Task 5.2: Catalog connection failure fallback test (Property 11)
    @given(catalog_lists())
    @hyp_settings(max_examples=50)
    async def test_catalog_connection_failure_fallback(self, items: List[CatalogItem]):
        """
        **Feature: docker-mcp-gateway-console, Property 11: Catalog connection failure fallback**
        
        If the connection to the Catalog URL fails, the system should fallback to cached data if available.
        """
        service = CatalogService()
        url = "http://test.url"
        
        # Pre-populate cache
        await service.update_cache(url, items)
        
        # Mock HTTP failure
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = Exception("Network Error")
            mock_instance.__aenter__.return_value = mock_instance
            MockClient.return_value = mock_instance

            # Should succeed using cache
            fetched_items, is_cached = await service.fetch_catalog(url)
            
            assert is_cached is True
            assert len(fetched_items) == len(items)
            assert fetched_items[0].id == items[0].id

    # Task 5.3: Keyword search property test (Property 26)
    @given(catalog_lists(), st.text(min_size=1))
    @hyp_settings(max_examples=100)
    async def test_keyword_search(self, items: List[CatalogItem], keyword: str):
        """
        **Feature: docker-mcp-gateway-console, Property 26: Keyword search**
        
        For any keyword, all search results should contain that keyword
        in either the name or description.
        """
        service = CatalogService()
        results = await service.search_catalog(items, query=keyword)
        
        keyword_lower = keyword.lower()
        for item in results:
            assert keyword_lower in item.name.lower() or keyword_lower in item.description.lower()

    # Task 5.4: Category filtering property test (Property 27)
    @given(catalog_lists(), st.text(min_size=1))
    @hyp_settings(max_examples=100)
    async def test_category_filtering(self, items: List[CatalogItem], category: str):
        """
        **Feature: docker-mcp-gateway-console, Property 27: Category filtering**
        
        For any category, filtering results should only contain items of that category.
        """
        service = CatalogService()
        results = await service.search_catalog(items, category=category)
        
        for item in results:
            assert item.category == category

    # Task 5.5: Search reset property test (Property 28)
    @given(catalog_lists())
    @hyp_settings(max_examples=50)
    async def test_search_reset(self, items: List[CatalogItem]):
        """
        **Feature: docker-mcp-gateway-console, Property 28: Search reset**
        
        Clearing the search query (passing empty string) should return all items (if no category filter).
        """
        service = CatalogService()
        results = await service.search_catalog(items, query="")
        
        assert len(results) == len(items)
        # Order might be preserved or not, but set of IDs should match
        assert {i.id for i in results} == {i.id for i in items}

    # Task 5.6: Compound filtering property test (Property 29)
    @given(catalog_lists(), st.text(min_size=1), st.text(min_size=1))
    @hyp_settings(max_examples=100)
    async def test_compound_filtering(self, items: List[CatalogItem], keyword: str, category: str):
        """
        **Feature: docker-mcp-gateway-console, Property 29: Compound filtering**
        
        When filtering by both keyword and category, results must satisfy BOTH conditions.
        """
        service = CatalogService()
        results = await service.search_catalog(items, query=keyword, category=category)
        
        keyword_lower = keyword.lower()
        for item in results:
            # Condition 1: Category match
            assert item.category == category
            # Condition 2: Keyword match
            assert keyword_lower in item.name.lower() or keyword_lower in item.description.lower()

