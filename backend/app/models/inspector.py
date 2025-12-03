"""Inspector models for MCP protocol communication."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolInfo(BaseModel):
    """Information about an MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any] = Field(default_factory=dict)


class ResourceInfo(BaseModel):
    """Information about an MCP resource."""
    uri: str
    name: str
    description: str
    mime_type: Optional[str] = None


class PromptInfo(BaseModel):
    """Information about an MCP prompt."""
    name: str
    description: str
    arguments: List[Dict[str, Any]] = Field(default_factory=list)


class InspectorResponse(BaseModel):
    """Response containing MCP server capabilities."""
    tools: List[ToolInfo] = Field(default_factory=list)
    resources: List[ResourceInfo] = Field(default_factory=list)
    prompts: List[PromptInfo] = Field(default_factory=list)
