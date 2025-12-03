"""Catalog API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..models.catalog import CatalogResponse, CatalogSearchRequest
from ..services.catalog import CatalogError, CatalogService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

# Initialize catalog service
catalog_service = CatalogService()


@router.get("", response_model=CatalogResponse)
async def get_catalog(
    source: str = Query(..., description="URL of the catalog JSON file")
) -> CatalogResponse:
    """
    Fetch catalog data from a remote source.
    
    This endpoint fetches the catalog of available MCP servers from the specified URL.
    If the fetch fails, it attempts to return cached data if available.
    
    Args:
        source: URL of the catalog JSON file
        
    Returns:
        CatalogResponse with list of available MCP servers
        
    Raises:
        HTTPException: If catalog cannot be fetched and no cache is available
    """
    try:
        # Check if we have valid cached data first
        cached_items = await catalog_service.get_cached_catalog(source)
        
        if cached_items is not None:
            # We have valid cache, try to fetch fresh data in background
            # but return cached data immediately
            try:
                items = await catalog_service.fetch_catalog(source)
                return CatalogResponse(
                    servers=items,
                    total=len(items),
                    cached=False
                )
            except CatalogError:
                # Fresh fetch failed, return cached data
                logger.info(f"Returning cached catalog for {source}")
                return CatalogResponse(
                    servers=cached_items,
                    total=len(cached_items),
                    cached=True
                )
        else:
            # No cache, must fetch fresh data
            items = await catalog_service.fetch_catalog(source)
            return CatalogResponse(
                servers=items,
                total=len(items),
                cached=False
            )
            
    except CatalogError as e:
        logger.error(f"Failed to fetch catalog: {e}")
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
    source: str = Query(..., description="URL of the catalog JSON file"),
    q: str = Query(default="", description="Search keyword"),
    category: Optional[str] = Query(default=None, description="Category filter")
) -> CatalogResponse:
    """
    Search and filter catalog items.
    
    This endpoint allows searching the catalog by keyword and filtering by category.
    The search looks for matches in both the name and description fields.
    
    Args:
        source: URL of the catalog JSON file
        q: Search keyword (searches in name and description)
        category: Category filter (exact match)
        
    Returns:
        CatalogResponse with filtered list of MCP servers
        
    Raises:
        HTTPException: If catalog cannot be fetched
    """
    try:
        # Fetch catalog data (will use cache if available)
        items = await catalog_service.fetch_catalog(source)
        
        # Apply search and filters
        filtered_items = await catalog_service.search_catalog(
            items=items,
            query=q,
            category=category
        )
        
        return CatalogResponse(
            servers=filtered_items,
            total=len(filtered_items),
            cached=False
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
