from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional
from ..models.containers import ContainerConfig, ContainerInfo, LogEntry

class ContainerProvider(ABC):
    """Abstract interface for container operations."""
    
    @property
    @abstractmethod
    def identifier(self) -> str:
        """Return a safe identifier for the provider (e.g., host or URL)."""
        pass

    @abstractmethod
    async def list_containers(self, all_containers: bool = True) -> List[ContainerInfo]:
        """List containers."""
        pass

    @abstractmethod
    async def create_container(
        self,
        config: ContainerConfig,
        sanitized_name: str,
        resolved_env: Dict[str, str],
    ) -> str:
        """Create and start a container."""
        pass

    @abstractmethod
    async def start_container(self, container_id: str) -> bool:
        """Start a container."""
        pass

    @abstractmethod
    async def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """Stop a container."""
        pass

    @abstractmethod
    async def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """Restart a container."""
        pass

    @abstractmethod
    async def delete_container(self, container_id: str, force: bool = False) -> bool:
        """Delete a container."""
        pass

    @abstractmethod
    async def stream_logs(
        self,
        container_id: str,
        follow: bool = True,
        tail: int = 100,
    ) -> AsyncIterator[LogEntry]:
        """Stream logs from a container."""
        pass

    @abstractmethod
    async def exec_command(
        self,
        container_id: str,
        command: List[str],
    ) -> tuple[int, bytes]:
        """Execute a command in a container."""
        pass

    @abstractmethod
    def close(self):
        """Close the provider connection."""
        pass
