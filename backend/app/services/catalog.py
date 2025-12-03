"""Catalog Service for MCP server catalog management."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx

from ..config import settings
from ..models.catalog import Catalog, CatalogItem

logger = logging.getLogger(__name__)


class CatalogError(Exception):
    """Custom exception for catalog-related errors."""
    pass


class CatalogService:
    """
    Manages MCP server catalog data.
    
    Responsibilities:
    - Fetch catalog data from remote URLs
    - Cache catalog data in memory
    - Search and filter catalog items
    - Handle connection failures with fallback to cache
    """

    def __init__(self):
        """Initialize the Catalog Service with empty cache."""
        # Cache structure: {source_url: (catalog_data, expiry_time)}
        self._cache: Dict[str, tuple[List[CatalogItem], datetime]] = {}
        self._cache_ttl = timedelta(seconds=settings.catalog_cache_ttl_seconds)

    async def fetch_catalog(self, source_url: str) -> List[CatalogItem]:
        """
        Fetch catalog data from a remote URL.
        
        This method attempts to fetch fresh catalog data from the specified URL.
        If the fetch fails, it falls back to cached data if available.
        
        Args:
            source_url: URL of the catalog JSON file
            
        Returns:
            List of CatalogItem objects
            
        Raises:
            CatalogError: If fetch fails and no cached data is available
        """
        try:
            # Try to fetch fresh data
            catalog_items = await self._fetch_from_url(source_url)
            
            # Update cache with fresh data
            await self.update_cache(source_url, catalog_items)
            
            logger.info(f"Successfully fetched catalog from {source_url}")
            return catalog_items
            
        except Exception as e:
            logger.warning(f"Failed to fetch catalog from {source_url}: {e}")
            
            # Try to use cached data as fallback
            cached_data = await self.get_cached_catalog(source_url)
            if cached_data is not None:
                logger.info(f"Using cached catalog data for {source_url}")
                return cached_data
            
            # No cache available, raise error
            raise CatalogError(
                f"Failed to fetch catalog from {source_url} and no cached data available: {e}"
            ) from e

    async def _fetch_from_url(self, source_url: str) -> List[CatalogItem]:
        """
        Fetch and parse catalog data from a URL.
        
        Args:
            source_url: URL of the catalog JSON file
            
        Returns:
            List of CatalogItem objects
            
        Raises:
            CatalogError: If fetch or parsing fails
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(source_url)
                response.raise_for_status()
                
                # Parse JSON response
                data = response.json()
                
                # Validate and parse catalog structure
                catalog = Catalog(**data)
                
                return catalog.servers
                
        except httpx.HTTPStatusError as e:
            raise CatalogError(
                f"HTTP error {e.response.status_code} while fetching catalog: {e}"
            ) from e
        except httpx.RequestError as e:
            raise CatalogError(
                f"Network error while fetching catalog: {e}"
            ) from e
        except json.JSONDecodeError as e:
            raise CatalogError(
                f"Invalid JSON in catalog response: {e}"
            ) from e
        except Exception as e:
            raise CatalogError(
                f"Failed to parse catalog data: {e}"
            ) from e

    async def get_cached_catalog(self, source_url: str) -> Optional[List[CatalogItem]]:
        """
        Retrieve catalog data from cache if available and not expired.
        
        Args:
            source_url: URL of the catalog (used as cache key)
            
        Returns:
            List of CatalogItem objects if cached and not expired, None otherwise
        """
        if source_url not in self._cache:
            return None
        
        catalog_items, expiry = self._cache[source_url]
        
        # Check if cache has expired
        if datetime.now() >= expiry:
            logger.debug(f"Cache expired for {source_url}")
            del self._cache[source_url]
            return None
        
        logger.debug(f"Cache hit for {source_url}")
        return catalog_items

    async def update_cache(
        self, 
        source_url: str, 
        items: List[CatalogItem]
    ) -> None:
        """
        Update the cache with fresh catalog data.
        
        Args:
            source_url: URL of the catalog (used as cache key)
            items: List of CatalogItem objects to cache
        """
        expiry = datetime.now() + self._cache_ttl
        self._cache[source_url] = (items, expiry)
        logger.debug(f"Updated cache for {source_url}, expires at {expiry}")

    async def search_catalog(
        self, 
        items: List[CatalogItem],
        query: str = "",
        category: Optional[str] = None
    ) -> List[CatalogItem]:
        """
        Search and filter catalog items.
        
        This method filters catalog items based on:
        - Keyword search in name or description
        - Category filter
        
        Args:
            items: List of CatalogItem objects to search
            query: Search keyword (searches in name and description)
            category: Category filter (exact match)
            
        Returns:
            Filtered list of CatalogItem objects
        """
        results = items
        
        # Apply keyword search
        if query:
            query_lower = query.lower()
            results = [
                item for item in results
                if query_lower in item.name.lower() 
                or query_lower in item.description.lower()
            ]
        
        # Apply category filter
        if category:
            results = [
                item for item in results
                if item.category == category
            ]
        
        logger.debug(
            f"Search results: {len(results)} items "
            f"(query='{query}', category='{category}')"
        )
        
        return results

    def clear_cache(self, source_url: Optional[str] = None) -> None:
        """
        Clear cached catalog data.
        
        Args:
            source_url: Specific URL to clear, or None to clear all cache
        """
        if source_url is None:
            self._cache.clear()
            logger.info("Cleared all catalog cache")
        elif source_url in self._cache:
            del self._cache[source_url]
            logger.info(f"Cleared cache for {source_url}")

    async def cleanup_expired_cache(self) -> int:
        """
        Remove all expired cache entries.
        
        Returns:
            Number of cache entries removed
        """
        now = datetime.now()
        expired_urls = []
        
        for url, (_, expiry) in self._cache.items():
            if now >= expiry:
                expired_urls.append(url)
        
        for url in expired_urls:
            del self._cache[url]
        
        if expired_urls:
            logger.info(f"Cleaned up {len(expired_urls)} expired cache entries")
        
        return len(expired_urls)
