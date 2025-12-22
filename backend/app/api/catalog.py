"""Catalog API endpoints."""

import asyncio
import logging
import math
from typing import Optional, Union

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse

from ..config import settings
from ..models.catalog import (
    CatalogErrorCode,
    CatalogErrorResponse,
    CatalogResponse,
    CatalogSourceId,
)
from ..services.catalog import CatalogError, CatalogService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

# Initialize catalog service
catalog_service = CatalogService()


def _resolve_source_id(source: Optional[str]) -> CatalogSourceId:
    """Resolve catalog source ID from query param."""
    if source is None:
        return CatalogSourceId.DOCKER
    try:
        return CatalogSourceId(source)
    except ValueError as exc:
        raise CatalogError(
            "Invalid source value. Allowed: docker, official",
            error_code=CatalogErrorCode.INVALID_SOURCE,
        ) from exc


def _resolve_source_url(source_id: CatalogSourceId) -> str:
    """Resolve source ID to upstream catalog URL."""
    mapping = {
        CatalogSourceId.DOCKER: settings.catalog_docker_url,
        CatalogSourceId.OFFICIAL: settings.catalog_official_url,
    }
    return mapping[source_id]


def _catalog_error_response(
    error: CatalogError, *, status_code: int
) -> JSONResponse:
    """Create structured error response for catalog errors."""
    payload = CatalogErrorResponse(
        detail=error.message,
        error_code=error.error_code,
        retry_after_seconds=error.retry_after_seconds,
    ).model_dump(mode="json", exclude_none=True)
    return JSONResponse(status_code=status_code, content=payload)


@router.get(
    "",
    response_model=CatalogResponse,
    responses={
        400: {
            "model": CatalogErrorResponse,
            "description": "Invalid request parameters (e.g., invalid source ID)",
        },
        503: {
            "description": "Service unavailable - failed to fetch catalog"
        },
    },
)
async def get_catalog(
    source: Optional[str] = Query(None, description="Catalog source ID")
) -> Union[CatalogResponse, JSONResponse]:
    """
    Fetch catalog data from a remote source.
    
    This endpoint fetches the catalog of available MCP servers from a preset source ID.
    If no source is provided, it uses the Docker catalog source.
    If the fetch fails, it attempts to return cached data if available.
    
    Args:
        source: Catalog source ID (optional)
        
    Returns:
        CatalogResponse with list of available MCP servers
        
    Raises:
        HTTPException: If catalog cannot be fetched and no cache is available
    """
    try:
        source_id = _resolve_source_id(source)
        source_url = _resolve_source_url(source_id)

        # Check if we have valid cached data first
        cached_items = await catalog_service.get_cached_catalog(source_url)
        warning_msg = str(catalog_service.warning) if catalog_service.warning else None

        if cached_items is not None:
            # We have valid cache, try to fetch fresh data in background
            # but return cached data immediately
            async def _background_fetch(url: str):
                try:
                    await catalog_service.fetch_catalog(url)
                except Exception as e:
                    logger.error(f"Background fetch failed for {url}: {e}")

            asyncio.create_task(_background_fetch(source_url))

            return CatalogResponse(
                servers=cached_items,
                total=len(cached_items),
                page=1,
                page_size=max(len(cached_items), 1),
                cached=True,
                categories=sorted({item.category for item in cached_items}),
                warning=warning_msg,
            )
        else:
            # No cache, must fetch fresh data
            items, is_cached = await catalog_service.fetch_catalog(source_url)
            warning_msg = str(catalog_service.warning) if catalog_service.warning else None
            return CatalogResponse(
                servers=items,
                total=len(items),
                page=1,
                page_size=max(len(items), 1),
                cached=is_cached,
                categories=sorted({item.category for item in items}),
                warning=warning_msg,
            )
            
    except CatalogError as e:
        logger.error(f"Failed to fetch catalog: {e}")
        if e.error_code == CatalogErrorCode.INVALID_SOURCE:
            return _catalog_error_response(
                e, status_code=status.HTTP_400_BAD_REQUEST
            )
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch catalog: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching catalog: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/search", response_model=CatalogResponse)
async def search_catalog(
    source: Optional[str] = Query(None, description="URL of the catalog JSON file"),
    q: str = Query(default="", description="Search keyword"),
    category: Optional[str] = Query(default=None, description="Category filter"),
    page: int = Query(default=1, ge=1, description="1始まりのページ番号"),
    page_size: int = Query(
        default=12,
        ge=1,
        le=200,
        description="1ページあたりの件数。過大指定での負荷を防ぐため上限200件。",
    ),
) -> CatalogResponse:
    """
    Search and filter catalog items.
    
    This endpoint allows searching the catalog by keyword and filtering by category.
    The search looks for matches in both the name and description fields.
    if no URL is provided, it uses the default registry URL.
    
    Args:
        source: URL of the catalog JSON file (optional)
        q: Search keyword (searches in name and description)
        category: Category filter (exact match)
        
    Returns:
        CatalogResponse with filtered list of MCP servers
        
    Raises:
        HTTPException: If catalog cannot be fetched
    """
    source_url = source or settings.catalog_default_url
    
    try:
        # Fetch catalog data (will use cache if available)
        items, is_cached = await catalog_service.fetch_catalog(source_url)
        
        # Apply search and filters
        filtered_items = await catalog_service.search_catalog(
            items=items,
            query=q,
            category=category
        )
        warning_msg = str(catalog_service.warning) if catalog_service.warning else None
        
        total = len(filtered_items)
        if total == 0:
            return CatalogResponse(
                servers=[],
                total=0,
                page=1,
                page_size=page_size,
                cached=is_cached,
                categories=[],
                warning=warning_msg,
            )

        max_page = max(1, math.ceil(total / page_size))
        current_page = min(page, max_page)
        start = (current_page - 1) * page_size
        end = start + page_size
        paged_items = filtered_items[start:end]
        categories = sorted({item.category for item in filtered_items})

        return CatalogResponse(
            servers=paged_items,
            total=total,
            page=current_page,
            page_size=page_size,
            cached=is_cached,
            categories=categories,
            warning=warning_msg,
        )
        
    except CatalogError as e:
        logger.error(f"Failed to search catalog: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch catalog for search: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error searching catalog: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.delete("/cache")
async def clear_catalog_cache(
    source: Optional[str] = Query(default=None, description="Specific catalog URL to clear, or omit to clear all")
) -> dict:
    """
    Clear catalog cache.
    
    This endpoint allows clearing the catalog cache, either for a specific source
    or for all sources.
    
    Args:
        source: Optional URL of specific catalog to clear, or None to clear all
        
    Returns:
        Success message
    """
    try:
        catalog_service.clear_cache(source)
        
        if source:
            return {"success": True, "message": f"Cache cleared for {source}"}
        else:
            return {"success": True, "message": "All catalog cache cleared"}
            
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear cache: {str(e)}"
        )
