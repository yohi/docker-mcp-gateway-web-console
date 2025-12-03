"""Container Service for Docker integration."""

import asyncio
from datetime import datetime
from typing import AsyncIterator, Dict, List, Optional

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound
from docker.models.containers import Container

from ..config import settings
from ..models.containers import (
    ContainerConfig,
    ContainerInfo,
    LogEntry,
)
from .secrets import SecretManager


class ContainerService:
    """
    Manages Docker container lifecycle operations.
    
    Responsibilities:
    - List all containers
    - Create and start containers with secret resolution
    - Stop, restart, and delete containers
    - Stream container logs
    """

    def __init__(self, secret_manager: SecretManager):
        """
        Initialize the Container Service.
        
        Args:
            secret_manager: SecretManager instance for resolving Bitwarden references
        """
        self.secret_manager = secret_manager
        self._client: Optional[docker.DockerClient] = None

    def _get_client(self) -> docker.DockerClient:
        """
        Get or create Docker client.
        
        Returns:
            Docker client instance
            
        Raises:
            RuntimeError: If Docker client cannot be created
        """
        if self._client is None:
            try:
                self._client = docker.DockerClient(base_url=settings.docker_host)
                # Test connection
                self._client.ping()
            except DockerException as e:
                raise RuntimeError(f"Failed to connect to Docker daemon: {e}") from e
        
        return self._client

    def _parse_container_status(self, container: Container) -> str:
        """
        Parse container status into simplified format.
        
        Args:
            container: Docker container object
            
        Returns:
            Status string: "running", "stopped", or "error"
        """
        status = container.status.lower()
        
        if status == "running":
            return "running"
        elif status in ["exited", "created", "paused"]:
            return "stopped"
        else:
            # dead, removing, restarting, etc.
            return "error"

    def _container_to_info(self, container: Container) -> ContainerInfo:
        """
        Convert Docker container object to ContainerInfo model.
        
        Args:
            container: Docker container object
            
        Returns:
            ContainerInfo model
        """
        # Parse creation timestamp
        created_str = container.attrs.get("Created", "")
        try:
            # Docker returns ISO format with nanoseconds
            created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            created_at = datetime.now()

        # Parse port mappings
        ports = {}
        port_bindings = container.attrs.get("NetworkSettings", {}).get("Ports", {})
        if port_bindings:
            for container_port, host_bindings in port_bindings.items():
                if host_bindings:
                    # Extract port number from format like "8080/tcp"
                    port_num = container_port.split("/")[0]
                    # Use first host binding
                    host_port = int(host_bindings[0]["HostPort"])
                    ports[port_num] = host_port

        # Get labels
        labels = container.labels or {}

        return ContainerInfo(
            id=container.id,
            name=container.name.lstrip("/"),  # Docker adds leading slash
            image=container.image.tags[0] if container.image.tags else container.image.id,
            status=self._parse_container_status(container),
            created_at=created_at,
            ports=ports,
            labels=labels,
        )

    async def list_containers(self, all_containers: bool = True) -> List[ContainerInfo]:
        """
        List all Docker containers.
        
        Args:
            all_containers: If True, include stopped containers. If False, only running.
            
        Returns:
            List of ContainerInfo objects
            
        Raises:
            RuntimeError: If Docker operation fails
        """
        try:
            client = self._get_client()
            
            # Run blocking Docker operation in thread pool
            loop = asyncio.get_event_loop()
            containers = await loop.run_in_executor(
                None,
                lambda: client.containers.list(all=all_containers)
            )
            
            return [self._container_to_info(c) for c in containers]
            
        except DockerException as e:
            raise RuntimeError(f"Failed to list containers: {e}") from e

    async def create_container(
        self,
        config: ContainerConfig,
        session_id: str,
        bw_session_key: str,
    ) -> str:
        """
        Create and start a Docker container with secret resolution.
        
        This method:
        1. Resolves all Bitwarden references in environment variables
        2. Creates the Docker container
        3. Starts the container
        4. Returns the container ID
        
        Args:
            config: Container configuration
            session_id: Session ID for secret caching
            bw_session_key: Bitwarden session key for authentication
            
        Returns:
            Container ID
            
        Raises:
            RuntimeError: If container creation or secret resolution fails
        """
        try:
            # Resolve all Bitwarden references in environment variables
            resolved_env = await self.secret_manager.resolve_all(
                config.env,
                session_id,
                bw_session_key,
            )
            
            client = self._get_client()
            
            # Prepare port bindings
            port_bindings = {}
            if config.ports:
                for container_port, host_port in config.ports.items():
                    port_bindings[f"{container_port}/tcp"] = host_port
            
            # Prepare volume bindings
            volumes = {}
            if config.volumes:
                for host_path, container_path in config.volumes.items():
                    volumes[host_path] = {
                        "bind": container_path,
                        "mode": "rw",
                    }
            
            # Create container
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                lambda: client.containers.create(
                    image=config.image,
                    name=config.name,
                    environment=resolved_env,
                    ports=port_bindings,
                    volumes=volumes,
                    labels=config.labels,
                    command=config.command,
                    network_mode=config.network_mode,
                    detach=True,
                ),
            )
            
            # Start the container
            await loop.run_in_executor(None, container.start)
            
            return container.id
            
        except ImageNotFound as e:
            raise RuntimeError(f"Docker image not found: {config.image}") from e
        except APIError as e:
            raise RuntimeError(f"Docker API error: {e}") from e
        except DockerException as e:
            raise RuntimeError(f"Failed to create container: {e}") from e
        except Exception as e:
            # Catch secret resolution errors
            raise RuntimeError(f"Failed to create container: {e}") from e

    async def start_container(self, container_id: str) -> bool:
        """
        Start a stopped container.
        
        Args:
            container_id: Container ID
            
        Returns:
            True if successful
            
        Raises:
            RuntimeError: If container not found or operation fails
        """
        try:
            client = self._get_client()
            
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                lambda: client.containers.get(container_id)
            )
            
            await loop.run_in_executor(None, container.start)
            
            return True
            
        except NotFound as e:
            raise RuntimeError(f"Container not found: {container_id}") from e
        except APIError as e:
            raise RuntimeError(f"Failed to start container: {e}") from e
        except DockerException as e:
            raise RuntimeError(f"Docker operation failed: {e}") from e

    async def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """
        Stop a running container.
        
        Args:
            container_id: Container ID
            timeout: Seconds to wait before killing the container
            
        Returns:
            True if successful
            
        Raises:
            RuntimeError: If container not found or operation fails
        """
        try:
            client = self._get_client()
            
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                lambda: client.containers.get(container_id)
            )
            
            await loop.run_in_executor(
                None,
                lambda: container.stop(timeout=timeout)
            )
            
            return True
            
        except NotFound as e:
            raise RuntimeError(f"Container not found: {container_id}") from e
        except APIError as e:
            raise RuntimeError(f"Failed to stop container: {e}") from e
        except DockerException as e:
            raise RuntimeError(f"Docker operation failed: {e}") from e

    async def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """
        Restart a container.
        
        Args:
            container_id: Container ID
            timeout: Seconds to wait before killing the container during stop
            
        Returns:
            True if successful
            
        Raises:
            RuntimeError: If container not found or operation fails
        """
        try:
            client = self._get_client()
            
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                lambda: client.containers.get(container_id)
            )
            
            await loop.run_in_executor(
                None,
                lambda: container.restart(timeout=timeout)
            )
            
            return True
            
        except NotFound as e:
            raise RuntimeError(f"Container not found: {container_id}") from e
        except APIError as e:
            raise RuntimeError(f"Failed to restart container: {e}") from e
        except DockerException as e:
            raise RuntimeError(f"Docker operation failed: {e}") from e

    async def delete_container(self, container_id: str, force: bool = False) -> bool:
        """
        Delete a container.
        
        Args:
            container_id: Container ID
            force: If True, force removal even if running
            
        Returns:
            True if successful
            
        Raises:
            RuntimeError: If container not found or operation fails
        """
        try:
            client = self._get_client()
            
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                lambda: client.containers.get(container_id)
            )
            
            await loop.run_in_executor(
                None,
                lambda: container.remove(force=force)
            )
            
            return True
            
        except NotFound as e:
            raise RuntimeError(f"Container not found: {container_id}") from e
        except APIError as e:
            raise RuntimeError(f"Failed to delete container: {e}") from e
        except DockerException as e:
            raise RuntimeError(f"Docker operation failed: {e}") from e

    async def stream_logs(
        self,
        container_id: str,
        follow: bool = True,
        tail: int = 100,
    ) -> AsyncIterator[LogEntry]:
        """
        Stream logs from a container.
        
        Args:
            container_id: Container ID
            follow: If True, stream logs in real-time
            tail: Number of lines to show from the end
            
        Yields:
            LogEntry objects
            
        Raises:
            RuntimeError: If container not found or operation fails
        """
        try:
            client = self._get_client()
            
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                lambda: client.containers.get(container_id)
            )
            
            # Get log stream
            log_stream = await loop.run_in_executor(
                None,
                lambda: container.logs(
                    stream=follow,
                    follow=follow,
                    tail=tail,
                    timestamps=True,
                    stdout=True,
                    stderr=True,
                )
            )
            
            # Process log lines
            for line in log_stream:
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                
                # Parse timestamp and message
                # Docker log format: "2024-01-01T12:00:00.000000000Z message"
                parts = line.strip().split(" ", 1)
                
                if len(parts) == 2:
                    timestamp_str, message = parts
                    try:
                        timestamp = datetime.fromisoformat(
                            timestamp_str.replace("Z", "+00:00")
                        )
                    except ValueError:
                        timestamp = datetime.now()
                        message = line.strip()
                else:
                    timestamp = datetime.now()
                    message = line.strip()
                
                # Determine stream (stdout vs stderr)
                # Docker SDK doesn't easily distinguish, default to stdout
                stream = "stdout"
                
                yield LogEntry(
                    timestamp=timestamp,
                    message=message,
                    stream=stream,
                )
                
        except NotFound as e:
            raise RuntimeError(f"Container not found: {container_id}") from e
        except APIError as e:
            raise RuntimeError(f"Failed to stream logs: {e}") from e
        except DockerException as e:
            raise RuntimeError(f"Docker operation failed: {e}") from e

    def close(self):
        """Close the Docker client connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
