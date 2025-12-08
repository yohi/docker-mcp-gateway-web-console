from typing import List
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
