"""Catalog models."""

from typing import Dict, List

from pydantic import BaseModel, Field


class CatalogItem(BaseModel):
    """Model for a single MCP server in the catalog."""
    id: str = Field(..., description="Unique identifier for the catalog item")
    name: str = Field(..., description="Display name of the MCP server")
    description: str = Field(..., description="Description of the MCP server")
    vendor: str = Field(default="", description="Vendor/Author of the MCP server")
    category: str = Field(..., description="Category (e.g., 'utilities', 'ai', 'data')")
    docker_image: str = Field(..., description="Docker image name and tag")
    icon_url: str = Field(default="", description="Icon URL for the MCP server")
    default_env: Dict[str, str] = Field(
        default_factory=dict,
        description="Default environment variables (may contain Bitwarden references)"
    )
    required_envs: List[str] = Field(
        default_factory=list,
        description="List of required environment variable names (secrets or not)"
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
    """カタログ検索結果レスポンス。"""

    servers: List[CatalogItem]
    total: int = Field(..., description="該当するサーバーの総数")
    page: int = Field(default=1, description="1始まりのページ番号")
    page_size: int = Field(default=0, description="1ページあたりの件数")
    cached: bool = Field(default=False, description="キャッシュ由来かどうか")
    categories: List[str] = Field(
        default_factory=list, description="結果集合に含まれるカテゴリ一覧（重複なし）"
    )
    warning: str | None = Field(
        default=None,
        description="取得時の警告メッセージ(例: GitHub トークン復号失敗によるフェールセーフ)。",
    )
