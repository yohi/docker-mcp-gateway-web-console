"""Catalog models."""

from typing import Dict, List

from pydantic import BaseModel, Field


class CatalogItem(BaseModel):
    """Model for a single MCP server in the catalog."""
    id: str = Field(..., description="Unique identifier for the catalog item")
    name: str = Field(..., description="Display name of the MCP server")
    description: str = Field(..., description="Description of the MCP server")
    category: str = Field(..., description="Category (e.g., 'utilities', 'ai', 'data')")
    docker_image: str = Field(..., description="Docker image name and tag")
    default_env: Dict[str, str] = Field(
        default_factory=dict,
        description="Default environment variables (may contain Bitwarden references)"
    )
    required_secrets: List[str] = Field(
        default_factory=list,
        description="List of environment variable names that require secrets"
    )


class Catalog(BaseModel):
    """Model for the complete catalog."""
    version: str = Field(..., description="Catalog format version")
    servers: List[CatalogItem] = Field(..., description="List of available MCP servers")


class CatalogSearchRequest(BaseModel):
    """Request model for catalog search."""
    query: str = Field(default="", description="Search keyword")
    category: str = Field(default="", description="Category filter")


class CatalogResponse(BaseModel):
    """Response model for catalog operations."""
    servers: List[CatalogItem]
    total: int = Field(..., description="Total number of servers in result")
    cached: bool = Field(default=False, description="Whether data is from cache")
