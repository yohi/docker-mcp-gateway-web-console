"""Docker SDK implementation of ContainerProvider."""

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional

import docker
from docker.errors import APIError, DockerException, ImageNotFound
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout as RequestsTimeout

from ..models.containers import (
    ContainerConfig,
    ContainerInfo,
    LogEntry,
)
from .base import ContainerProvider
from .containers import ContainerUnavailableError

logger = logging.getLogger(__name__)

def _parse_version_triplet(value: str) -> Optional[tuple[int, int, int]]:
    match = re.match(r"^\s*(\d+)\.(\d+)(?:\.(\d+))?", value)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))

def ensure_docker_unix_adapter() -> None:
    """Patch docker's UnixHTTPAdapter for requests 2.32.x compatibility."""
    try:
        from docker.transport import unixconn
        from requests.adapters import HTTPAdapter
        import requests
    except Exception:
        return

    docker_version = _parse_version_triplet(getattr(docker, "__version__", ""))
    if docker_version is not None and docker_version >= (7, 1, 0):
        return

    requests_version = _parse_version_triplet(getattr(requests, "__version__", ""))
    if requests_version is None or requests_version < (2, 32, 0) or requests_version >= (2, 33, 0):
        return

    if not hasattr(unixconn.UnixHTTPAdapter, "get_connection_with_tls_context"):
        def _get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
            return self.get_connection(request.url, proxies)
        unixconn.UnixHTTPAdapter.get_connection_with_tls_context = _get_connection_with_tls_context

    if hasattr(HTTPAdapter, "get_connection_with_tls_context"):
        original = HTTPAdapter.get_connection_with_tls_context
        if not getattr(original, "_docker_http_compat", False):
            def _patched_get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
                url = getattr(request, "url", "") or ""
                if url.startswith("http+docker://") or url.startswith("http+unix://"):
                    return self.get_connection(url, proxies)
                return original(self, request, verify, proxies=proxies, cert=cert)
            _patched_get_connection_with_tls_context._docker_http_compat = True
            HTTPAdapter.get_connection_with_tls_context = _patched_get_connection_with_tls_context

ensure_docker_unix_adapter()

class DockerProviderError(Exception):
    """Base exception for Docker provider."""
    pass

class DockerUnavailableError(ContainerUnavailableError):
    """Raised when Docker daemon is unreachable."""
    def __init__(self, attempted_hosts: list[str], errors: list[str]) -> None:
        super().__init__(attempted_hosts, errors)
        self.status_code = 503

class DockerSdkProvider(ContainerProvider):
    """Docker SDK based implementation of ContainerProvider."""

    def __init__(
        self,
        base_url: str,
        tls_config: Optional[docker.tls.TLSConfig] = None,
    ):
        self.base_url = base_url
        self.tls_config = tls_config
        self._client: Optional[docker.DockerClient] = None
        self._last_error: Optional[DockerUnavailableError] = None
        self._last_error_at: Optional[float] = None

    @property
    def identifier(self) -> str:
        """Return the base URL as the provider identifier."""
        return self.base_url

    async def _get_client(self) -> docker.DockerClient:
        """Get or create the Docker client in a thread-safe way."""
        if self._client:
            return self._client

        if self._last_error and self._last_error_at:
            if time.monotonic() - self._last_error_at < 5:
                raise self._last_error

        def _init_client():
            attempted_hosts = [self.base_url]
            errors = []
            try:
                client = docker.DockerClient(base_url=self.base_url, tls=self.tls_config)
                client.ping()
                return client, attempted_hosts
            except DockerException as e:
                errors.append(f"{self.base_url}: {e}")
            raise DockerUnavailableError(attempted_hosts, errors)

        loop = asyncio.get_event_loop()
        try:
            client, _ = await loop.run_in_executor(None, _init_client)
            self._client = client
            return self._client
        except DockerUnavailableError as e:
            self._last_error = e
            self._last_error_at = time.monotonic()
            raise

    async def _call_docker_api(self, func, *args, **kwargs):
        """Wrap Docker API calls to normalize connection errors and clear cached client."""
        await self._get_client()
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
        except (DockerException, APIError, RequestsConnectionError, RequestsTimeout, ConnectionError, TimeoutError) as e:
            # If it's a connection-related error, invalidate the client
            if "connection" in str(e).lower() or "timeout" in str(e).lower() or isinstance(e, (RequestsConnectionError, RequestsTimeout, ConnectionError, TimeoutError)):
                self._client = None
                # Wrap as DockerUnavailableError to normalize
                raise DockerUnavailableError([self.base_url], [str(e)]) from e
            raise

    def _container_summary_to_info(self, summary: dict[str, Any]) -> ContainerInfo:
        container_id = summary.get("Id") or summary.get("ID")
        names = summary.get("Names") or []
        name = names[0].lstrip("/") if names else str(container_id)
        
        labels = summary.get("Labels") or {}
        # docker-mcp-name ラベルがある場合はそれを表示名に使用する
        display_name = labels.get("docker-mcp-name") or labels.get("mcp.original_name") or name

        created_raw = summary.get("Created")
        created_at = datetime.now(timezone.utc)
        if isinstance(created_raw, (int, float)):
            created_at = datetime.fromtimestamp(created_raw, tz=timezone.utc)

        ports: dict[str, int] = {}
        for port in summary.get("Ports") or []:
            if isinstance(port, dict):
                p_port = port.get("PrivatePort")
                pub_port = port.get("PublicPort")
                if p_port and pub_port:
                    ports[str(p_port)] = int(pub_port)

        state = str(summary.get("State") or summary.get("Status") or "").lower()
        status = "running" if state == "running" else ("stopped" if state in {"exited", "created", "paused"} else "error")

        return ContainerInfo(
            id=str(container_id),
            name=name,
            image=str(summary.get("Image") or ""),
            status=status,
            created_at=created_at,
            ports=ports,
            labels=summary.get("Labels") or {},
        )

    async def list_containers(self, all_containers: bool = True) -> List[ContainerInfo]:
        client = await self._get_client()
        summaries = await self._call_docker_api(client.api.containers, all=all_containers)
        return [self._container_summary_to_info(s) for s in summaries]

    async def create_container(self, config: ContainerConfig, sanitized_name: str, resolved_env: Dict[str, str]) -> str:
        client = await self._get_client()

        # Image pull logic
        try:
            await self._call_docker_api(client.images.get, config.image)
        except ImageNotFound:
            await self._call_docker_api(client.images.pull, config.image)

        port_bindings = {f"{cp}/tcp": hp for cp, hp in (config.ports or {}).items()}
        volumes = {hp: {"bind": cp, "mode": "rw"} for hp, cp in (config.volumes or {}).items()}
        
        labels = dict(config.labels or {})
        if sanitized_name != config.name:
            labels["mcp.original_name"] = config.name

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
            "cpus": config.cpus,
            "mem_limit": config.memory_limit,
            "restart_policy": config.restart_policy,
        }
        
        loop = asyncio.get_event_loop()
        container = None
        
        def _create_and_start():
            nonlocal container
            container = client.containers.create(
                **{k: v for k, v in docker_kwargs.items() if v is not None}
            )
            container.start()
            return container.id

        try:
            return await loop.run_in_executor(None, _create_and_start)
        except (DockerException, APIError, RequestsConnectionError, RequestsTimeout, ConnectionError, TimeoutError) as e:
            # Normalize connection-related errors similar to _call_docker_api
            if "connection" in str(e).lower() or "timeout" in str(e).lower() or isinstance(e, (RequestsConnectionError, RequestsTimeout, ConnectionError, TimeoutError)):
                self._client = None
                # Ensure any container leftover is removed before raising normalized error
                if container:
                    try:
                        await loop.run_in_executor(None, lambda: container.remove(force=True))
                    except Exception as cleanup_exc:
                        logger.warning(f"Failed to remove orphaned container {container.id} after connection error: {cleanup_exc}")
                raise DockerUnavailableError([self.base_url], [str(e)]) from e
            
            # Non-connection Docker errors (like 409) still need cleanup
            if container:
                try:
                    await loop.run_in_executor(None, lambda: container.remove(force=True))
                except Exception as cleanup_exc:
                    logger.warning(f"Failed to remove orphaned container {container.id} after Docker error: {cleanup_exc}")
            raise
        except Exception:
            # Other general errors
            if container:
                try:
                    await loop.run_in_executor(None, lambda: container.remove(force=True))
                except Exception as cleanup_exc:
                    logger.warning(f"Failed to remove orphaned container {container.id} after error: {cleanup_exc}")
            raise

    async def start_container(self, container_id: str) -> bool:
        client = await self._get_client()
        container = await self._call_docker_api(client.containers.get, container_id)
        await self._call_docker_api(container.start)
        return True

    async def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        client = await self._get_client()
        container = await self._call_docker_api(client.containers.get, container_id)
        await self._call_docker_api(container.stop, timeout=timeout)
        return True

    async def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        client = await self._get_client()
        container = await self._call_docker_api(client.containers.get, container_id)
        await self._call_docker_api(container.restart, timeout=timeout)
        return True

    async def delete_container(self, container_id: str, force: bool = False) -> bool:
        client = await self._get_client()
        container = await self._call_docker_api(client.containers.get, container_id)
        await self._call_docker_api(container.remove, force=force)
        return True

    async def stream_logs(self, container_id: str, follow: bool = True, tail: int = 100) -> AsyncIterator[LogEntry]:
        client = await self._get_client()
        container = await self._call_docker_api(client.containers.get, container_id)
        
        log_stream = await self._call_docker_api(
            container.logs,
            stream=follow, follow=follow, tail=tail, timestamps=True, stdout=True, stderr=True, demux=True
        )

        def get_next():
            try:
                return next(log_stream, None)
            except StopIteration:
                return None

        while True:
            chunk = await asyncio.get_event_loop().run_in_executor(None, get_next)
            if chunk is None:
                break
            
            stdout_chunk, stderr_chunk = chunk
            if stdout_chunk:
                raw, stream = stdout_chunk.decode("utf-8", errors="replace"), "stdout"
            elif stderr_chunk:
                raw, stream = stderr_chunk.decode("utf-8", errors="replace"), "stderr"
            else:
                continue

            parts = raw.strip().split(" ", 1)
            if len(parts) == 2:
                ts_str, msg = parts
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except ValueError:
                    ts, msg = datetime.now(), raw.strip()
            else:
                ts, msg = datetime.now(), raw.strip()

            yield LogEntry(timestamp=ts, message=msg, stream=stream)

    async def exec_command(self, container_id: str, command: List[str]) -> tuple[int, bytes]:
        client = await self._get_client()
        container = await self._call_docker_api(client.containers.get, container_id)
        exit_code, output = await self._call_docker_api(container.exec_run, cmd=command, stdout=True, stderr=True)
        return exit_code or 0, output or b""


    def close(self):
        if self._client:
            self._client.close()
            self._client = None
