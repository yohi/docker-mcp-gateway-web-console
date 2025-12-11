"""Catalog Service for MCP server catalog management."""

import asyncio
import base64
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
import yaml

from ..config import settings
from ..models.catalog import Catalog, CatalogItem
from ..schemas.catalog import RegistryItem
from .github_token import GitHubTokenError, GitHubTokenService

logger = logging.getLogger(__name__)

LEGACY_RAW_URL = "https://raw.githubusercontent.com/docker/mcp-registry/main/registry.json"
# servers 配列探索時の再帰最大深度。設定値が存在すればそれを利用する。
DEFAULT_SERVER_SEARCH_MAX_DEPTH = 64
SERVER_SEARCH_MAX_DEPTH = max(
    1, getattr(settings, "catalog_server_search_max_depth", DEFAULT_SERVER_SEARCH_MAX_DEPTH)
)


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
        self._github_token_service = GitHubTokenService()
        self._github_fetch_concurrency = max(
            1, getattr(settings, "catalog_github_fetch_concurrency", 8)
        )
        self._github_fetch_retries = max(
            1, getattr(settings, "catalog_github_fetch_retries", 2)
        )
        self._github_fetch_retry_base_delay = max(
            0.1, getattr(settings, "catalog_github_fetch_retry_base_delay_seconds", 0.5)
        )
        self._warning: Optional[str] = None

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

    async def fetch_catalog(
        self, source_url: str, force_refresh: bool = False
    ) -> Tuple[List[CatalogItem], bool]:
        """
        カタログデータを取得する。メモリキャッシュが有効な場合はAPI呼び出しをスキップする。

        Args:
            source_url: 取得先のURL
            force_refresh: True の場合はキャッシュを無視して強制的に取得する

        Returns:
            (CatalogItemのリスト, キャッシュ利用フラグ)

        Raises:
            CatalogError: 取得およびフォールバックが失敗し、キャッシュも無い場合
        """
        if not force_refresh:
            cached = await self.get_cached_catalog(source_url)
            if cached is not None:
                logger.debug(f"Using cached catalog for {source_url}")
                return cached, True

        try:
            # Try to fetch fresh data
            catalog_items = await self._fetch_from_url(source_url)

            # Update cache with fresh data
            await self.update_cache(source_url, catalog_items)

            logger.info(f"Successfully fetched catalog from {source_url}")
            return catalog_items, False

        except Exception as e:
            if source_url in {LEGACY_RAW_URL, settings.catalog_default_url}:
                # primary失敗時はもう片方へフェイルオーバー
                fallback = (
                    settings.catalog_default_url
                    if source_url == LEGACY_RAW_URL
                    else LEGACY_RAW_URL
                )
                try:
                    logger.info(
                        f"Primary catalog URL {source_url} failed; falling back to {fallback}"
                    )
                    catalog_items = await self._fetch_from_url(fallback)
                    await self.update_cache(fallback, catalog_items)
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

    @property
    def warning(self) -> Optional[str]:
        """直近の警告（GitHub トークン復号失敗など）を返す。"""
        return self._warning

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
                response = await client.get(
                    source_url,
                    headers=self._github_headers(source_url),
                )
                response.raise_for_status()

                # Parse JSON response
                data = response.json()

                # Validate and parse catalog structure
                if isinstance(data, list):
                    # GitHub contents API 形式 (https://api.github.com/repos/docker/mcp-registry/contents/servers)
                    if self._is_github_contents_payload(data):
                        dir_items = [
                            item
                            for item in data
                            if isinstance(item, dict) and item.get("type") == "dir"
                        ]

                        semaphore = asyncio.Semaphore(self._github_fetch_concurrency)
                        tasks = [
                            self._fetch_github_server_yaml_with_limit(
                                semaphore, client, item
                            )
                            for item in dir_items
                        ]
                        results = await asyncio.gather(*tasks, return_exceptions=True)

                        converted: List[CatalogItem] = []
                        for item, result in zip(dir_items, results):
                            if isinstance(result, Exception) or result is None:
                                converted.append(self._convert_github_content_item(item))
                            else:
                                converted.append(result)
                        return converted

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

    def _is_github_contents_payload(self, data: List[Any]) -> bool:
        """
        GitHub Contents API の形式かどうかを判定する。
        """
        if not data:
            return False

        return all(
            isinstance(item, dict)
            and {"name", "path", "type", "html_url"}.issubset(item.keys())
            for item in data
        )

    def _convert_github_content_item(self, item: dict) -> CatalogItem:
        """
        GitHub Contents API のエントリを CatalogItem に変換する。
        """
        name = item.get("name") or "unknown"
        path = item.get("path") or name
        html_url = item.get("html_url") or ""

        description = f"docker/mcp-registry: {path}"
        vendor = "docker"

        return CatalogItem(
            id=name,
            name=name,
            description=description,
            vendor=vendor,
            category="general",
            docker_image="",
            icon_url="",
            default_env={},
            required_envs=[],
            required_secrets=[],
        )

    async def _fetch_github_server_yaml_with_limit(
        self, semaphore: asyncio.Semaphore, client: httpx.AsyncClient, item: dict
    ) -> Optional[CatalogItem]:
        """GitHub server.yaml 取得時の並列度を制御する。"""
        async with semaphore:
            return await self._fetch_github_server_yaml(client, item)

    def _should_retry_github(self, error: Exception) -> bool:
        """GitHub API 取得のリトライ可否を判定する。"""
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code in {429, 500, 502, 503, 504}
        if isinstance(error, httpx.RequestError):
            return True
        return False

    async def _fetch_github_server_yaml(
        self, client: httpx.AsyncClient, item: dict
    ) -> Optional[CatalogItem]:
        """
        GitHub Contents API のディレクトリエントリから server.yaml を取得し、CatalogItem に変換する。
        """
        path = item.get("path")
        if not path:
            return None

        server_yaml_url = f"https://api.github.com/repos/docker/mcp-registry/contents/{path}/server.yaml"

        delay = self._github_fetch_retry_base_delay
        last_error: Optional[Exception] = None

        for attempt in range(self._github_fetch_retries):
            try:
                response = await client.get(
                    server_yaml_url,
                    headers=self._github_headers(server_yaml_url),
                )
                if response.status_code == 404:
                    return None

                response.raise_for_status()
                payload = response.json()
                content = payload.get("content")
                if not content:
                    return None

                decoded = base64.b64decode(content)
                data = yaml.safe_load(decoded) or {}

                name = (
                    data.get("about", {}).get("title")
                    or data.get("name")
                    or item.get("name")
                    or "unknown"
                )
                description = (
                    data.get("about", {}).get("description")
                    or data.get("meta", {}).get("description")
                    or f"docker/mcp-registry: {path}"
                )
                vendor = (
                    data.get("source", {}).get("project")
                    or data.get("meta", {}).get("vendor")
                    or "docker"
                )
                category = data.get("meta", {}).get("category") or "general"
                docker_image = data.get("image") or ""
                icon_url = (
                    data.get("about", {}).get("icon")
                    or data.get("meta", {}).get("icon")
                    or ""
                )

                required_envs: List[str] = data.get("required_envs") or []
                if not isinstance(required_envs, list):
                    required_envs = []
                required_secrets = [
                    env for env in required_envs if self._is_secret_env(env)
                ]

                return CatalogItem(
                    id=item.get("name") or name,
                    name=name,
                    description=description,
                    vendor=vendor,
                    category=category,
                    docker_image=docker_image,
                    icon_url=icon_url,
                    default_env={},
                    required_envs=required_envs,
                    required_secrets=required_secrets,
                )
            except Exception as e:
                last_error = e
                should_retry = self._should_retry_github(e) and attempt < (
                    self._github_fetch_retries - 1
                )
                if should_retry:
                    logger.debug(
                        f"Retrying server.yaml fetch for {path}: {e} "
                        f"(attempt {attempt + 2}/{self._github_fetch_retries})"
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self._github_fetch_retry_base_delay * 4)
                    continue

                logger.warning(f"Failed to fetch server.yaml for {path}: {e}")
                return None

        if last_error:
            logger.warning(f"Failed to fetch server.yaml for {path}: {last_error}")
        return None

    def _github_headers(self, url: str) -> Dict[str, str]:
        """
        GitHub API へのアクセス時に Authorization ヘッダーを付与する。
        """
        if "api.github.com" not in url:
            return {}
        try:
            token = self._github_token_service.get_active_token()
        except GitHubTokenError as exc:
            self._warning = (
                "保存済み GitHub トークンの復号に失敗したため、未認証でカタログを取得しています。"
                " トークンを再保存するか環境変数 GITHUB_TOKEN を設定してください。"
            )
            logger.warning(
                "GitHub token decrypt failed; falling back to unauthenticated catalog fetch: %s",
                exc,
            )
            return {}

        if token:
            self._warning = None
            return {"Authorization": f"Bearer {token}"}

        # トークン未設定の場合は警告をクリアして匿名取得
        self._warning = None
        return {}

    def _extract_servers(self, data: Any, depth: int = 0) -> Optional[List[dict]]:
        """
        外部レジストリレスポンスから servers 配列を抽出する。
        深さが SERVER_SEARCH_MAX_DEPTH を超えた場合は探索を打ち切る。
        """
        if depth >= SERVER_SEARCH_MAX_DEPTH:
            return None

        if isinstance(data, dict):
            if "servers" in data and isinstance(data["servers"], list):
                return data["servers"]
            for v in data.values():
                res = self._extract_servers(v, depth + 1)
                if res is not None:
                    return res
        elif isinstance(data, list):
            for v in data:
                res = self._extract_servers(v, depth + 1)
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
                icon_url=server_data.get("icon", ""),
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
            icon_url=item.get("icon", ""),
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
