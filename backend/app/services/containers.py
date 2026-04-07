"""Container Service for Docker integration."""

import asyncio
import logging
import re
from typing import AsyncIterator, List, Optional

from ..models.containers import (
    ContainerConfig,
    ContainerInfo,
    LogEntry,
)
from ..models.state import ContainerConfigRecord
from .base import ContainerProvider
from .secrets import SecretManager
from .state_store import StateStore


class ContainerError(Exception):
    """Exception raised for container operation errors."""
    pass


class ContainerUnavailableError(ContainerError):
    """Exception raised when Docker daemon is unavailable."""

    def __init__(self, attempted_hosts: list[str], errors: list[str]) -> None:
        self.attempted_hosts = attempted_hosts
        self.errors = errors
        message = (
            "Docker デーモンに接続できません。"
            f" 試行した DOCKER_HOST: {', '.join(attempted_hosts)}。"
            f" 詳細: {' | '.join(errors)}"
        )
        super().__init__(message)


class ContainerAlreadyExistsError(ContainerError):
    """Exception raised when a container with the same name already exists."""

    def __init__(
        self,
        name: str,
        container_id: str | None = None,
        status: str | None = None,
    ) -> None:
        self.name = name
        self.container_id = container_id
        self.status = status

        detail = f"コンテナ名 {name} は既に使用されています。"
        if container_id:
            detail += f" 既存コンテナID: {container_id}。"
        if status:
            detail += f" 状態: {status}。"

        super().__init__(detail)


class ContainerService:
    """
    Manages Docker container lifecycle operations using a ContainerProvider.
    
    Responsibilities:
    - List all containers
    - Create and start containers with secret resolution
    - Stop, restart, and delete containers
    - Stream container logs
    """

    def __init__(
        self,
        provider: ContainerProvider,
        secret_manager: SecretManager,
        state_store: Optional[StateStore] = None
    ):
        """
        Initialize the Container Service.
        
        Args:
            provider: ContainerProvider instance for actual operations
            secret_manager: SecretManager instance for resolving Bitwarden references
            state_store: StateStore instance for persisting container configurations
        """
        self.provider = provider
        self.secret_manager = secret_manager
        self._state_store = state_store or StateStore()

    def _normalize_container_name(self, name: str) -> str:
        """
        Normalize container name for Docker.
        """
        normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip())
        normalized = normalized.strip("._-")
        if not normalized:
            normalized = "mcp-server"
        if not re.match(r"^[A-Za-z0-9]", normalized):
            normalized = f"mcp-{normalized}"
            normalized = normalized.strip("._-")
            if not normalized:
                normalized = "mcp-server"
        return normalized[:63]

    async def list_containers(self, all_containers: bool = True) -> List[ContainerInfo]:
        """List containers via provider."""
        try:
            return await self.provider.list_containers(all_containers=all_containers)
        except Exception as e:
            raise ContainerError(f"Failed to list containers: {e}") from e

    async def create_container(
        self,
        config: ContainerConfig,
        session_id: str,
        bw_session_key: str,
    ) -> str:
        """Create and start a container with secret resolution."""
        try:
            # Resolve secrets
            resolved_env = await self.secret_manager.resolve_all(
                config.env,
                session_id,
                bw_session_key,
            )

            sanitized_name = self._normalize_container_name(config.name)

            # Create and start via provider
            container_id = await self.provider.create_container(
                config,
                sanitized_name,
                resolved_env,
            )
            
            # Save state
            try:
                self._state_store.save_container_config(
                    ContainerConfigRecord(
                        container_id=container_id,
                        name=sanitized_name,
                        image=config.image,
                        config=config.model_dump(),
                    )
                )
            except Exception as store_exc:
                logging.getLogger(__name__).warning(
                    "コンテナ設定の保存に失敗しました: %s", store_exc
                )

            return container_id
            
        except Exception as e:
            raise ContainerError(f"Failed to create container: {e}") from e

    def get_container_config(self, container_id: str) -> dict:
        """Return saved container configuration."""
        record = self._state_store.get_container_config(container_id)
        if record is None:
            raise ContainerError("コンテナ設定が保存されていません")
        return record.config

    async def exec_command(
        self,
        container_id: str,
        command: List[str],
    ) -> tuple[int, bytes]:
        """Execute command in container via provider."""
        try:
            return await self.provider.exec_command(container_id, command)
        except Exception as e:
            raise ContainerError(f"Failed to exec command: {e}") from e

    async def start_container(self, container_id: str) -> bool:
        """Start container via provider."""
        try:
            return await self.provider.start_container(container_id)
        except Exception as e:
            raise ContainerError(f"Failed to start container: {e}") from e

    async def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """Stop container via provider."""
        try:
            return await self.provider.stop_container(container_id, timeout=timeout)
        except Exception as e:
            raise ContainerError(f"Failed to stop container: {e}") from e

    async def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """Restart container via provider."""
        try:
            return await self.provider.restart_container(container_id, timeout=timeout)
        except Exception as e:
            raise ContainerError(f"Failed to restart container: {e}") from e

    async def delete_container(self, container_id: str, force: bool = False) -> bool:
        """Delete container via provider."""
        try:
            return await self.provider.delete_container(container_id, force=force)
        except Exception as e:
            raise ContainerError(f"Failed to delete container: {e}") from e

    async def stream_logs(
        self,
        container_id: str,
        follow: bool = True,
        tail: int = 100,
    ) -> AsyncIterator[LogEntry]:
        """Stream logs via provider."""
        try:
            async for entry in self.provider.stream_logs(container_id, follow, tail):
                yield entry
        except Exception as e:
            raise ContainerError(f"Failed to stream logs: {e}") from e

    def close(self):
        """Close provider."""
        if self.provider:
            self.provider.close()
