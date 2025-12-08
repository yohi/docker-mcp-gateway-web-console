"""Catalog Service for MCP server catalog management."""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ..config import settings
from ..models.catalog import Catalog, CatalogItem
from ..schemas.catalog import RegistryItem

logger = logging.getLogger(__name__)

LEGACY_RAW_URL = "https://raw.githubusercontent.com/docker/mcp-registry/main/registry.json"


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

    @staticmethod
    def _is_secret_env(key: str) -> bool:
        """環境変数名からシークレットかどうかを推測する。"""
        upper = key.upper()
        return (
            "KEY" in upper
            or "SECRET" in upper
            or "TOKEN" in upper
            or "PASSWORD" in upper
        )

    async def fetch_catalog(self, source_url: str) -> Tuple[List[CatalogItem], bool]:
        """
        Fetch catalog data from a remote URL.

        This method attempts to fetch fresh catalog data from the specified URL.
        If the fetch fails, it falls back to cached data if available.

        Args:
            source_url: URL of the catalog JSON file

        Returns:
            Tuple containing:
            - List of CatalogItem objects
            - Boolean indicating if data is from cache (True) or fresh (False)

        Raises:
            CatalogError: If fetch fails and no cached data is available
        """
        try:
            # Try to fetch fresh data
            catalog_items = await self._fetch_from_url(source_url)

            # Update cache with fresh data
            await self.update_cache(source_url, catalog_items)

            logger.info(f"Successfully fetched catalog from {source_url}")
            return catalog_items, False

        except Exception as e:
            if source_url == LEGACY_RAW_URL:
                try:
                    logger.info(
                        f"Primary catalog URL {source_url} failed; falling back to {settings.catalog_default_url}"
                    )
                    catalog_items = await self._fetch_from_url(settings.catalog_default_url)
                    await self.update_cache(settings.catalog_default_url, catalog_items)
                    return catalog_items, False
                except Exception as fe:
                    logger.warning(f"Fallback fetch failed: {fe}")

            logger.warning(f"Failed to fetch catalog from {source_url}: {e}")

            # Try to use cached data as fallback
            cached_data = await self.get_cached_catalog(source_url)
            if cached_data is not None:
                logger.info(f"Using cached catalog data for {source_url}")
                return cached_data, True

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
                if isinstance(data, list):
                    # New Registry format (list of RegistryItem)
                    items: List[CatalogItem] = []
                    for item_data in data:
                        try:
                            # Parse as RegistryItem first to validate
                            reg_item = RegistryItem(**item_data)
                            # Convert to internal CatalogItem
                            required_envs = reg_item.required_envs
                            required_secrets = [
                                env for env in required_envs if self._is_secret_env(env)
                            ]
                            items.append(CatalogItem(
                                id=reg_item.name,
                                name=reg_item.name,
                                description=reg_item.description,
                                vendor=reg_item.vendor or "",
                                category="general",  # Default category
                                docker_image=reg_item.image,
                                default_env={},
                                required_envs=required_envs,
                                required_secrets=required_secrets
                            ))
                        except Exception as e:
                            logger.warning(f"Skipping invalid registry item: {e}")
                    return items
                else:
                    # Attempt to parse Hub explore.data structure
                    servers = self._extract_servers(data)
                    if servers is not None:
                        return [self._convert_explore_server(item) for item in servers if item]

                    # Legacy or Catalog format
                    catalog = Catalog(**data)
                    return catalog.servers

        except httpx.HTTPStatusError as e:
            raise CatalogError(
                f"HTTP error {e.response.status_code} while fetching catalog: {e}"
            ) from e
        except httpx.RequestError as e:
            raise CatalogError(f"Network error while fetching catalog: {e}") from e
        except json.JSONDecodeError as e:
            raise CatalogError(f"Invalid JSON in catalog response: {e}") from e
        except Exception as e:
            raise CatalogError(f"Failed to parse catalog data: {e}") from e

    def _extract_servers(self, data: Any) -> Optional[List[dict]]:
        """
        外部レジストリレスポンスから servers 配列を抽出する。
        """
        if isinstance(data, dict):
            if "servers" in data and isinstance(data["servers"], list):
                return data["servers"]
            for v in data.values():
                res = self._extract_servers(v)
                if res is not None:
                    return res
        elif isinstance(data, list):
            for v in data:
                res = self._extract_servers(v)
                if res is not None:
                    return res
        return None

    def _convert_explore_server(self, item: dict) -> CatalogItem:
        """
        外部レジストリのサーバー要素を CatalogItem に変換する。
        registry.modelcontextprotocol.io 形式と旧 hub explore 形式の両方を扱う。
        """
        # MCP Registry (registry.modelcontextprotocol.io) 形式
        if isinstance(item, dict) and isinstance(item.get("server"), dict):
            server_data = item["server"]
            name = server_data.get("name") or "unknown"
            description = server_data.get("description") or ""

            repository = server_data.get("repository") or {}
            vendor = ""
            if isinstance(repository, dict):
                vendor = repository.get("source") or repository.get("url") or ""
            if not vendor and "/" in name:
                vendor = name.split("/")[0]

            packages = server_data.get("packages") or []
            docker_image = ""
            if isinstance(packages, list):
                for pkg in packages:
                    if not isinstance(pkg, dict):
                        continue
                    identifier = pkg.get("identifier") or ""
                    registry_type = (
                        pkg.get("registryType") or pkg.get("type") or ""
                    ).lower()
                    if registry_type == "oci" and identifier:
                        docker_image = identifier
                        break
                    if not docker_image and identifier:
                        docker_image = identifier

            default_env = server_data.get("default_env")
            if not isinstance(default_env, dict):
                default_env = {}

            required_envs = server_data.get("required_envs") or []
            if not isinstance(required_envs, list):
                required_envs = []
            required_secrets = [
                env for env in required_envs if self._is_secret_env(env)
            ]

            return CatalogItem(
                id=name,
                name=name,
                description=description,
                vendor=vendor,
                category=server_data.get("category", "general"),
                docker_image=docker_image,
                default_env=default_env,
                required_envs=required_envs,
                required_secrets=required_secrets,
            )

        def _slug(text: str) -> str:
            s = re.sub(r"\s+", "-", text.strip().lower())
            return re.sub(r"[^a-z0-9_-]", "", s)

        title = item.get("title") or item.get("name") or "unknown"
        slug = item.get("slug") or item.get("id") or _slug(title)
        image = item.get("image") or item.get("container") or ""
        vendor = item.get("owner") or item.get("publisher") or ""
        description = item.get("description") or ""

        secrets = item.get("secrets", [])
        required_envs: List[str] = []
        required_secrets: List[str] = []
        if isinstance(secrets, list):
            for s in secrets:
                if isinstance(s, dict):
                    env_name = s.get("env") or s.get("name")
                    if env_name:
                        required_envs.append(env_name)
                        required_secrets.append(env_name)
                elif isinstance(s, str):
                    required_envs.append(s)
                    required_secrets.append(s)

        return CatalogItem(
            id=slug,
            name=title,
            description=description,
            vendor=vendor,
            category=item.get("category", "general"),
            docker_image=image,
            default_env={},
            required_envs=required_envs,
            required_secrets=required_secrets,
        )

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

    async def update_cache(self, source_url: str, items: List[CatalogItem]) -> None:
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
        self, items: List[CatalogItem], query: str = "", category: Optional[str] = None
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
                item
                for item in results
                if query_lower in item.name.lower() or query_lower in item.description.lower()
            ]

        # Apply category filter
        if category:
            results = [item for item in results if item.category == category]

        logger.debug(
            f"Search results: {len(results)} items " f"(query='{query}', category='{category}')"
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
