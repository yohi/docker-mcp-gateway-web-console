from typing import List, Optional
from pydantic import BaseModel, Field

class RegistryItem(BaseModel):
    """
    Model representing an MCP server in the external registry.
    """
    name: str = Field(..., description="Name of the MCP server")
    description: str = Field(..., description="Description of the server")
    vendor: str = Field(..., description="Vendor/Author of the server")
    image: str = Field(..., description="Docker image name")
    required_envs: List[str] = Field(default_factory=list, description="List of required environment variables")
    oauth_authorize_url: Optional[str] = Field(default=None, description="OAuth authorize URL (optional)")
    oauth_token_url: Optional[str] = Field(default=None, description="OAuth token URL (optional)")
    oauth_client_id: Optional[str] = Field(default=None, description="OAuth client_id (optional)")
    oauth_redirect_uri: Optional[str] = Field(default=None, description="OAuth redirect_uri (optional)")
