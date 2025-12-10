"""Container models."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ContainerConfig(BaseModel):
    """Configuration for creating a Docker container."""
    name: str = Field(..., description="Container name")
    image: str = Field(..., description="Docker image to use")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables (may contain Bitwarden references)")
    ports: Dict[str, int] = Field(default_factory=dict, description="Port mappings (container_port: host_port)")
    volumes: Dict[str, str] = Field(default_factory=dict, description="Volume mappings (host_path: container_path)")
    labels: Dict[str, str] = Field(default_factory=dict, description="Container labels")
    command: Optional[List[str]] = Field(default=None, description="Command to run in container")
    network_mode: Optional[str] = Field(default=None, description="Network mode (e.g., 'bridge', 'host')")
    cpus: Optional[float] = Field(
        default=None, description="CPU quota (e.g., 0.5 means half a core)"
    )
    memory_limit: Optional[str] = Field(
        default=None, description="Memory limit (Docker mem_limit, e.g., '512m')"
    )
    restart_policy: Optional[Dict[str, str]] = Field(
        default=None, description="Docker restart policy dictionary"
    )


class ContainerInfo(BaseModel):
    """Information about a Docker container."""
    id: str = Field(..., description="Container ID")
    name: str = Field(..., description="Container name")
    image: str = Field(..., description="Docker image")
    status: Literal["running", "stopped", "error"] = Field(..., description="Container status")
    created_at: datetime = Field(..., description="Container creation timestamp")
    ports: Dict[str, int] = Field(default_factory=dict, description="Port mappings")
    labels: Dict[str, str] = Field(default_factory=dict, description="Container labels")


class ContainerCreateResponse(BaseModel):
    """Response after creating a container."""
    container_id: str = Field(..., description="Created container ID")
    name: str = Field(..., description="Container name")
    status: str = Field(..., description="Container status")


class ContainerActionResponse(BaseModel):
    """Response for container actions (start, stop, restart, delete)."""
    success: bool = Field(..., description="Whether the action succeeded")
    message: str = Field(..., description="Action result message")
    container_id: Optional[str] = Field(default=None, description="Container ID")


class LogEntry(BaseModel):
    """A single log entry from a container."""
    timestamp: datetime = Field(..., description="Log entry timestamp")
    message: str = Field(..., description="Log message")
    stream: Literal["stdout", "stderr"] = Field(..., description="Output stream")


class ContainerListResponse(BaseModel):
    """Response containing list of containers."""
    containers: List[ContainerInfo] = Field(..., description="List of containers")
