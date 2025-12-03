"""Gateway configuration models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ServerConfig(BaseModel):
    """Configuration for a single MCP server."""
    
    name: str = Field(..., description="Server name")
    container_id: str = Field(..., description="Docker container ID")
    enabled: bool = Field(default=True, description="Whether the server is enabled")
    config: Dict[str, Any] = Field(default_factory=dict, description="Server-specific configuration")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate server name is not empty."""
        if not v or not v.strip():
            raise ValueError("Server name cannot be empty")
        return v.strip()
    
    @field_validator('container_id')
    @classmethod
    def validate_container_id(cls, v: str) -> str:
        """Validate container ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Container ID cannot be empty")
        return v.strip()


class GatewayConfig(BaseModel):
    """Gateway configuration model."""
    
    version: str = Field(default="1.0", description="Configuration version")
    servers: List[ServerConfig] = Field(default_factory=list, description="List of MCP servers")
    global_settings: Dict[str, Any] = Field(default_factory=dict, description="Global settings")
    
    @field_validator('version')
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version format."""
        if not v or not v.strip():
            raise ValueError("Version cannot be empty")
        return v.strip()


class ConfigReadResponse(BaseModel):
    """Response model for reading configuration."""
    
    config: GatewayConfig


class ConfigWriteRequest(BaseModel):
    """Request model for writing configuration."""
    
    config: GatewayConfig


class ConfigWriteResponse(BaseModel):
    """Response model for writing configuration."""
    
    success: bool
    message: str = "Configuration saved successfully"


class ValidationResult(BaseModel):
    """Result of configuration validation."""
    
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
