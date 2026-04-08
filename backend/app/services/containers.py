"""Container Service for Docker integration."""

import logging
import re
from typing import Any, AsyncIterator, List, Optional, TYPE_CHECKING

from fastapi import HTTPException, status

from ..models.containers import (
    ContainerConfig,
    ContainerInfo,
    LogEntry,
)
from ..models.state import ContainerConfigRecord
from .base import ContainerProvider
from .secrets import SecretManager
from .state_store import StateStore

if TYPE_CHECKING:
    from .auth import AuthService


class ContainerError(Exception):
    """Exception raised for container operation errors."""
    pass


class AuthenticationError(ContainerError):
    """Exception raised when authentication fails."""
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
        container_status: str | None = None,
    ) -> None:
        self.name = name
        self.container_id = container_id
        self.container_status = container_status

        detail = f"コンテナ名 {name} は既に使用されています。"
        if container_id:
            detail += f" 既存コンテナID: {container_id}。"
        if container_status:
            detail += f" 状態: {container_status}。"

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
        auth_service: "AuthService",
        state_store: Optional[StateStore] = None
    ):
        """
        Initialize the Container Service.
        
        Args:
            provider: ContainerProvider instance for actual operations
            secret_manager: SecretManager instance for resolving Bitwarden references
            auth_service: AuthService instance for session validation
            state_store: StateStore instance for persisting container configurations
        """
        self.provider = provider
        self.secret_manager = secret_manager
        self.auth_service = auth_service
        self._state_store = state_store or StateStore()

    async def _validate_session_and_get(self, session_id: str) -> Any:
        """Validate session and return the session model."""
        session = await self.auth_service.get_session(session_id)
        if session is None:
            raise AuthenticationError("Invalid or expired session")
        return session

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

    def _handle_provider_exception(self, e: Exception, operation: str) -> None:
        """Handle provider exceptions and wrap them in ContainerError."""
        if isinstance(e, ContainerUnavailableError):
            raise e

        st = getattr(e, "status_code", None)
        if st == 503:
            provider_id = self.provider.identifier
            raise ContainerUnavailableError([provider_id], [f"status={st}, error={e}"]) from e

        raise ContainerError(f"Failed to {operation}: {e}") from e

    def _map_container_error_to_http(self, e: ContainerError) -> Exception:
        """Map specific ContainerError types to FastAPI HTTPException.
        
        Other errors (including ContainerUnavailableError) are returned as-is
        so the API layer can handle them gracefully.
        """
        if isinstance(e, AuthenticationError):
            return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
        if isinstance(e, ContainerAlreadyExistsError):
            return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        
        # Return original domain exception for other ContainerError subclasses
        return e

    async def list_containers(self, all_containers: bool = True) -> List[ContainerInfo]:
        """List containers via provider."""
        try:
            return await self.provider.list_containers(all_containers=all_containers)
        except Exception as e:
            self._handle_provider_exception(e, "list containers")

    async def list_containers_with_auth(
        self, session_id: str, all_containers: bool = True
    ) -> List[ContainerInfo]:
        """Validate session before listing containers."""
        try:
            await self._validate_session_and_get(session_id)
            return await self.list_containers(all_containers)
        except ContainerError as e:
            raise self._map_container_error_to_http(e)

    async def create_container(
        self,
        config: ContainerConfig,
        session_id: str,
        bw_session_key: str,
    ) -> str:
        """Create and start a container with secret resolution."""
        # Resolve secrets
        resolved_env = await self.secret_manager.resolve_all(
            config.env,
            session_id,
            bw_session_key,
        )

        sanitized_name = self._normalize_container_name(config.name)

        try:
            # Create and start via provider
            container_id = await self.provider.create_container(
                config,
                sanitized_name,
                resolved_env,
            )
        except (ContainerAlreadyExistsError, ContainerUnavailableError):
            raise
        except Exception as e:
            st = getattr(e, "status_code", None)
            if st == 409:
                raise ContainerAlreadyExistsError(sanitized_name, container_status=str(st)) from e
            if st == 503:
                provider_id = self.provider.identifier
                raise ContainerUnavailableError([provider_id], [f"status={st}, error={e}"]) from e
            self._handle_provider_exception(e, "create container")
            
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
            logging.getLogger(__name__).error(
                "コンテナ設定の保存に失敗しました。クリーンアップを実行します: %s", store_exc
            )
            # クリーンアップ: 作成したコンテナを削除
            try:
                await self.delete_container(container_id, force=True)
            except Exception as cleanup_exc:
                logging.getLogger(__name__).error(
                    "クリーンアップ中のコンテナ削除に失敗しました: %s", cleanup_exc
                )
            raise ContainerError(f"Failed to save container state: {store_exc}") from store_exc

        return container_id

    async def create_container_with_auth(
        self,
        config: ContainerConfig,
        session_id: str,
    ) -> str:
        """Validate session before creating a container."""
        try:
            session = await self._validate_session_and_get(session_id)
            if not session.bw_session_key:
                raise ContainerError("Bitwarden session key not found in session")

            return await self.create_container(config, session_id, session.bw_session_key)
        except ContainerError as e:
            raise self._map_container_error_to_http(e)

    async def get_container_config_with_auth(
        self, 
        container_id: str, 
        session_id: str
    ) -> dict:
        """認証後に保存済みのコンテナ設定を返す。"""
        try:
            await self._validate_session_and_get(session_id)
            return self.get_container_config(container_id)
        except ContainerError as e:
            raise self._map_container_error_to_http(e)

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
            self._handle_provider_exception(e, "exec command")

    async def start_container(self, container_id: str) -> bool:
        """Start container via provider."""
        try:
            return await self.provider.start_container(container_id)
        except Exception as e:
            self._handle_provider_exception(e, "start container")

    async def start_container_with_auth(self, container_id: str, session_id: str) -> bool:
        """Validate session before starting a container."""
        try:
            await self._validate_session_and_get(session_id)
            return await self.start_container(container_id)
        except ContainerError as e:
            raise self._map_container_error_to_http(e)

    async def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """Stop container via provider."""
        try:
            return await self.provider.stop_container(container_id, timeout=timeout)
        except Exception as e:
            self._handle_provider_exception(e, "stop container")

    async def stop_container_with_auth(
        self, container_id: str, session_id: str, timeout: int = 10
    ) -> bool:
        """Validate session before stopping a container."""
        try:
            await self._validate_session_and_get(session_id)
            return await self.stop_container(container_id, timeout)
        except ContainerError as e:
            raise self._map_container_error_to_http(e)

    async def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """Restart container via provider."""
        try:
            return await self.provider.restart_container(container_id, timeout=timeout)
        except Exception as e:
            self._handle_provider_exception(e, "restart container")

    async def restart_container_with_auth(
        self, container_id: str, session_id: str, timeout: int = 10
    ) -> bool:
        """Validate session before restarting a container."""
        try:
            await self._validate_session_and_get(session_id)
            return await self.restart_container(container_id, timeout)
        except ContainerError as e:
            raise self._map_container_error_to_http(e)

    async def delete_container(self, container_id: str, force: bool = False) -> bool:
        """Delete container via provider."""
        try:
            return await self.provider.delete_container(container_id, force=force)
        except Exception as e:
            self._handle_provider_exception(e, "delete container")

    async def delete_container_with_auth(
        self, container_id: str, session_id: str, force: bool = False
    ) -> bool:
        """Validate session before deleting a container."""
        try:
            await self._validate_session_and_get(session_id)
            return await self.delete_container(container_id, force)
        except ContainerError as e:
            raise self._map_container_error_to_http(e)

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
            self._handle_provider_exception(e, "stream logs")

    def close(self):
        """Close provider."""
        if self.provider:
            self.provider.close()
