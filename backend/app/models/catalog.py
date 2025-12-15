"""Catalog models."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator


class CatalogItem(BaseModel):
    """Model for a single MCP server in the catalog."""
    id: str = Field(..., description="Unique identifier for the catalog item")
    name: str = Field(..., description="Display name of the MCP server")
    description: str = Field(..., description="Description of the MCP server")
    vendor: str = Field(default="", description="Vendor/Author of the MCP server")
    category: str = Field(..., description="Category (e.g., 'utilities', 'ai', 'data')")
    docker_image: Optional[str] = Field(
        default=None,
        description="Docker image name and tag. Preferred over remote_endpoint when present.",
    )
    server_type: Optional[str] = Field(
        default=None,
        description="Server type classification: 'docker' or 'remote'. Derived if not provided.",
    )
    remote_endpoint: Optional[HttpUrl] = Field(
        default=None,
        description="Remote MCP server SSE endpoint (used when docker_image is absent).",
    )
    is_remote: bool = Field(
        default=False,
        description="Derived flag indicating the item represents a remote (non-Docker) server.",
    )
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
    oauth_authorize_url: str | None = Field(
        default=None,
        description="OAuth authorize endpoint URL (server-specific override)",
    )
    oauth_token_url: str | None = Field(
        default=None,
        description="OAuth token endpoint URL (server-specific override)",
    )
    oauth_client_id: str | None = Field(
        default=None,
        description="OAuth client_id (server-specific override)",
    )
    oauth_redirect_uri: str | None = Field(
        default=None,
        description="OAuth redirect_uri (server-specific override)",
    )
    oauth_config: Optional[dict] = Field(
        default=None,
        description="OAuth configuration payload for remote servers.",
    )

    @model_validator(mode="after")
    def _derive_remote_flags(self) -> "CatalogItem":
        """Derive server_type and is_remote based on available endpoints."""
        has_docker = bool((self.docker_image or "").strip())
        has_remote = self.remote_endpoint is not None

        if has_docker:
            self.server_type = "docker"
            self.is_remote = False
        elif has_remote:
            self.server_type = "remote"
            self.is_remote = True
        else:
            # Neither docker_image nor remote_endpoint provided; keep defaults
            self.is_remote = False

        return self


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
