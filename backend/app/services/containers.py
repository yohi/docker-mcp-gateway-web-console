"""Container Service for Docker integration."""

import asyncio
import logging
import os
import re
import time
from datetime import datetime
from typing import AsyncIterator, Dict, List, Optional
from urllib.parse import urlparse

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


class ContainerError(Exception):
    """Exception raised for container operation errors."""
    pass


class ContainerUnavailableError(ContainerError):
    """Docker デーモンに接続できない場合の例外。"""

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
    """同名コンテナが既に存在する場合の例外。"""

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
        self._last_client_error: Optional[ContainerUnavailableError] = None
        self._last_client_error_at: Optional[float] = None

    def _normalize_container_name(self, name: str) -> str:
        """
        Docker が受け付ける形式へコンテナ名を正規化する。
        空白や禁則文字はハイフンに置換し、先頭が英数字でなければ接頭辞を付与する。
        DNS ラベル上限 (63 文字) に収まるよう短縮する。
        """
        # 空白や許可されない文字をハイフンに置換
        normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", name.strip())
        # 先頭末尾のドット/ハイフン/アンダースコアは除去
        normalized = normalized.strip("._-")
        if not normalized:
            normalized = "mcp-server"
        if not re.match(r"[a-zA-Z0-9]", normalized[0]):
            normalized = f"mcp-{normalized}"
        # DNS ラベルの実務上の上限に合わせて短縮
        return normalized[:63]

    def _get_client(self) -> docker.DockerClient:
        """
        Get or create Docker client.
        
        Returns:
            Docker client instance
            
        Raises:
            ContainerError: If Docker client cannot be created
        """
        if self._client is not None:
            return self._client

        # 直近の失敗をキャッシュし、連続リクエストでの遅延を避ける
        if self._last_client_error and self._last_client_error_at:
            if time.monotonic() - self._last_client_error_at < 30:
                raise self._last_client_error

        attempted_hosts: list[str] = [settings.docker_host]
        # 一般的なデフォルトソケットを常に最後のフォールバックとして試行する
        default_unix = "unix:///var/run/docker.sock"
        if default_unix not in attempted_hosts:
            attempted_hosts.append(default_unix)
        if settings.docker_host.startswith("unix://"):
            runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
            if runtime_dir:
                fallback = f"unix://{runtime_dir}/docker.sock"
                if fallback not in attempted_hosts:
                    attempted_hosts.append(fallback)
            try:
                uid = os.getuid()
            except AttributeError:
                uid = None
            if isinstance(uid, int):
                fallback_user = f"unix:///run/user/{uid}/docker.sock"
                if fallback_user not in attempted_hosts:
                    attempted_hosts.append(fallback_user)

        errors: list[str] = []
        for host in attempted_hosts:
            parsed = urlparse(host)
            socket_path = parsed.path if parsed.scheme == "unix" else None
            if socket_path:
                if not os.path.exists(socket_path):
                    errors.append(f"{host}: ソケット {socket_path} が見つかりません")
                    continue
                if not os.access(socket_path, os.R_OK | os.W_OK):
                    errors.append(
                        f"{host}: ソケット {socket_path} へのアクセス権限が不足しています"
                    )
                    continue

            try:
                client = docker.DockerClient(base_url=host)
                client.ping()
                self._client = client
                self._last_client_error = None
                self._last_client_error_at = None

                if host != settings.docker_host:
                    logging.getLogger(__name__).warning(
                        "DOCKER_HOST %s で接続できなかったため %s にフォールバックしました。"
                        " 環境変数 DOCKER_HOST または DOCKER_SOCKET_PATH を確認してください。",
                        settings.docker_host,
                        host,
                    )

                return self._client

            except DockerException as e:
                errors.append(f"{host}: {e}")

        error = ContainerUnavailableError(attempted_hosts, errors)
        self._last_client_error = error
        self._last_client_error_at = time.monotonic()
        raise error

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
            ContainerError: If Docker operation fails
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
            
        except ContainerUnavailableError:
            raise
        except DockerException as e:
            raise ContainerError(f"Failed to list containers: {e}") from e

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
            ContainerError: If container creation or secret resolution fails
        """
        try:
            # Resolve all Bitwarden references in environment variables
            resolved_env = await self.secret_manager.resolve_all(
                config.env,
                session_id,
                bw_session_key,
            )

            # Docker 名禁則の対策（カタログ名に空白が含まれるケースなど）
            sanitized_name = self._normalize_container_name(config.name)

            # ラベルに元の名称を残しつつ、元の labels を上書きしないようにコピー
            labels: dict[str, str] = dict(config.labels or {})
            if sanitized_name != config.name:
                labels.setdefault("mcp.original_name", config.name)
            
            client = self._get_client()
            loop = asyncio.get_event_loop()

            # イメージが未取得の場合は事前に pull して不足エラーを避ける
            try:
                await loop.run_in_executor(
                    None, lambda: client.images.get(config.image)
                )
            except ImageNotFound:
                try:
                    await loop.run_in_executor(
                        None, lambda: client.images.pull(config.image)
                    )
                except ImageNotFound as e:
                    raise ContainerError(f"Docker image not found: {config.image}") from e
                except APIError as e:
                    raise ContainerError(
                        f"Docker image pull failed: {config.image} ({e.explanation or e})"
                    ) from e
                except DockerException as e:
                    raise ContainerError(
                        f"Failed to pull Docker image: {config.image} ({e})"
                    ) from e
            
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

            docker_kwargs = {
                "image": config.image,
                "name": sanitized_name,
                "environment": resolved_env,
                "ports": port_bindings,
                "volumes": volumes,
                "labels": labels,
                "command": config.command,
                "network_mode": config.network_mode,
                "detach": True,
            }

            if config.cpus is not None:
                docker_kwargs["cpus"] = config.cpus
            if config.memory_limit is not None:
                docker_kwargs["mem_limit"] = config.memory_limit
            if config.restart_policy:
                docker_kwargs["restart_policy"] = config.restart_policy

            # Create container
            container = await loop.run_in_executor(
                None,
                lambda: client.containers.create(**docker_kwargs),
            )
            
            # Start the container
            await loop.run_in_executor(None, container.start)
            
            return container.id
            
        except ContainerUnavailableError:
            raise
        except ImageNotFound as e:
            raise ContainerError(f"Docker image not found: {config.image}") from e
        except APIError as e:
            if e.status_code == 409:
                existing_id: str | None = None
                existing_status: str | None = None

                try:
                    existing = await loop.run_in_executor(
                        None,
                        lambda: client.containers.list(
                            all=True, filters={"name": f"^{sanitized_name}$"}
                        ),
                    )
                    if existing:
                        for container in existing:
                            if container.name == sanitized_name:
                                existing_id = container.id
                                existing_status = self._parse_container_status(container)
                                break
                except DockerException as lookup_error:
                    logging.getLogger(__name__).debug(
                        "コンテナ重複確認中にエラーが発生しました: %s", lookup_error
                    )

                raise ContainerAlreadyExistsError(
                    name=sanitized_name,
                    container_id=existing_id,
                    status=existing_status,
                ) from e

            raise ContainerError(f"Docker API error: {e}") from e
        except DockerException as e:
            raise ContainerError(f"Failed to create container: {e}") from e
        except Exception as e:
            # Catch secret resolution errors
            raise ContainerError(f"Failed to create container: {e}") from e

    async def exec_command(
        self,
        container_id: str,
        command: List[str],
    ) -> tuple[int, bytes]:
        """
        コンテナ内でコマンドを実行し、終了コードと出力を返す。

        Args:
            container_id: 対象コンテナ ID
            command: 実行するコマンド配列

        Returns:
            (exit_code, combined_output) のタプル

        Raises:
            ContainerError: コンテナが存在しない場合、または Docker 実行に失敗した場合
        """
        try:
            client = self._get_client()
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                lambda: client.containers.get(container_id)
            )

            exit_code, output = await loop.run_in_executor(
                None,
                lambda: container.exec_run(
                    cmd=command,
                    stdout=True,
                    stderr=True,
                    demux=False,
                ),
            )

            if output is None:
                combined_output = b""
            elif isinstance(output, (bytes, bytearray)):
                combined_output = bytes(output)
            else:
                combined_output = str(output).encode("utf-8", errors="replace")

            return (exit_code or 0, combined_output)

        except ContainerUnavailableError:
            raise
        except NotFound as e:
            raise ContainerError(f"Container not found: {container_id}") from e
        except APIError as e:
            raise ContainerError(f"Docker API error: {e}") from e
        except DockerException as e:
            raise ContainerError(f"Failed to exec command: {e}") from e

    async def start_container(self, container_id: str) -> bool:
        """
        Start a stopped container.
        
        Args:
            container_id: Container ID
            
        Returns:
            True if successful
            
        Raises:
            ContainerError: If container not found or operation fails
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
            
        except ContainerUnavailableError:
            raise
        except NotFound as e:
            raise ContainerError(f"Container not found: {container_id}") from e
        except APIError as e:
            raise ContainerError(f"Failed to start container: {e}") from e
        except DockerException as e:
            raise ContainerError(f"Docker operation failed: {e}") from e

    async def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """
        Stop a running container.
        
        Args:
            container_id: Container ID
            timeout: Seconds to wait before killing the container
            
        Returns:
            True if successful
            
        Raises:
            ContainerError: If container not found or operation fails
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
            
        except ContainerUnavailableError:
            raise
        except NotFound as e:
            raise ContainerError(f"Container not found: {container_id}") from e
        except APIError as e:
            raise ContainerError(f"Failed to stop container: {e}") from e
        except DockerException as e:
            raise ContainerError(f"Docker operation failed: {e}") from e

    async def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """
        Restart a container.
        
        Args:
            container_id: Container ID
            timeout: Seconds to wait before killing the container during stop
            
        Returns:
            True if successful
            
        Raises:
            ContainerError: If container not found or operation fails
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
            
        except ContainerUnavailableError:
            raise
        except NotFound as e:
            raise ContainerError(f"Container not found: {container_id}") from e
        except APIError as e:
            raise ContainerError(f"Failed to restart container: {e}") from e
        except DockerException as e:
            raise ContainerError(f"Docker operation failed: {e}") from e

    async def delete_container(self, container_id: str, force: bool = False) -> bool:
        """
        Delete a container.
        
        Args:
            container_id: Container ID
            force: If True, force removal even if running
            
        Returns:
            True if successful
            
        Raises:
            ContainerError: If container not found or operation fails
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
            
        except ContainerUnavailableError:
            raise
        except NotFound as e:
            raise ContainerError(f"Container not found: {container_id}") from e
        except APIError as e:
            raise ContainerError(f"Failed to delete container: {e}") from e
        except DockerException as e:
            raise ContainerError(f"Docker operation failed: {e}") from e

    async def _read_log_line(self, log_stream):
        """Read a single log line in thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: next(log_stream, None)
        )

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
            ContainerError: If container not found or operation fails
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
                    demux=True,
                )
            )
            
            # Process log lines asynchronously
            while True:
                chunk = await self._read_log_line(log_stream)
                if chunk is None:
                    break
                
                # chunk is (stdout_bytes, stderr_bytes)
                stdout_chunk, stderr_chunk = chunk
                
                if stdout_chunk:
                    raw_line = stdout_chunk.decode("utf-8", errors="replace")
                    stream = "stdout"
                elif stderr_chunk:
                    raw_line = stderr_chunk.decode("utf-8", errors="replace")
                    stream = "stderr"
                else:
                    continue
                
                # Parse timestamp and message
                # Docker log format: "2024-01-01T12:00:00.000000000Z message"
                parts = raw_line.strip().split(" ", 1)
                
                if len(parts) == 2:
                    timestamp_str, message = parts
                    try:
                        timestamp = datetime.fromisoformat(
                            timestamp_str.replace("Z", "+00:00")
                        )
                    except ValueError:
                        timestamp = datetime.now()
                        message = raw_line.strip()
                else:
                    timestamp = datetime.now()
                    message = raw_line.strip()
                
                yield LogEntry(
                    timestamp=timestamp,
                    message=message,
                    stream=stream,
                )
                
        except ContainerUnavailableError:
            raise
        except NotFound as e:
            raise ContainerError(f"Container not found: {container_id}") from e
        except APIError as e:
            raise ContainerError(f"Failed to stream logs: {e}") from e
        except DockerException as e:
            raise ContainerError(f"Docker operation failed: {e}") from e

    def close(self):
        """Close the Docker client connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
