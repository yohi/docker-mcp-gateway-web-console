"""Docker SDK implementation of ContainerProvider."""

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional
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
from .base import ContainerProvider

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

class DockerUnavailableError(DockerProviderError):
    """Raised when Docker daemon is unreachable."""
    def __init__(self, attempted_hosts: list[str], errors: list[str]) -> None:
        self.attempted_hosts = attempted_hosts
        self.errors = errors
        message = f"Docker connection failed. Hosts: {attempted_hosts}. Errors: {errors}"
        super().__init__(message)

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

    def _get_client(self) -> docker.DockerClient:
        if self._client:
            return self._client

        if self._last_error and self._last_error_at:
            if time.monotonic() - self._last_error_at < 30:
                raise self._last_error

        attempted_hosts = [self.base_url]

        errors = []
        for host in attempted_hosts:
            parsed = urlparse(host)
            if parsed.scheme == "unix":
                socket_path = parsed.path
                if not os.path.exists(socket_path) or not os.access(socket_path, os.R_OK | os.W_OK):
                    errors.append(f"{host}: Socket inaccessible")
                    continue

            try:
                client = docker.DockerClient(base_url=host, tls=self.tls_config)
                client.ping()
                self._client = client
                return self._client
            except DockerException as e:
                errors.append(f"{host}: {e}")

        error = DockerUnavailableError(attempted_hosts, errors)
        self._last_error = error
        self._last_error_at = time.monotonic()
        raise error

    def _container_summary_to_info(self, summary: dict[str, Any]) -> ContainerInfo:
        container_id = summary.get("Id") or summary.get("ID")
        names = summary.get("Names") or []
        name = names[0].lstrip("/") if names else str(container_id)
        
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
        client = self._get_client()
        loop = asyncio.get_event_loop()
        summaries = await loop.run_in_executor(None, lambda: client.api.containers(all=all_containers))
        return [self._container_summary_to_info(s) for s in summaries]

    async def create_container(self, config: ContainerConfig, sanitized_name: str, resolved_env: Dict[str, str]) -> str:
        client = self._get_client()
        loop = asyncio.get_event_loop()

        # Image pull logic
        try:
            await loop.run_in_executor(None, lambda: client.images.get(config.image))
        except ImageNotFound:
            await loop.run_in_executor(None, lambda: client.images.pull(config.image))

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
        
        container = await loop.run_in_executor(None, lambda: client.containers.create(**{k: v for k, v in docker_kwargs.items() if v is not None}))
        await loop.run_in_executor(None, container.start)
        return container.id

    async def start_container(self, container_id: str) -> bool:
        client = self._get_client()
        loop = asyncio.get_event_loop()
        container = await loop.run_in_executor(None, lambda: client.containers.get(container_id))
        await loop.run_in_executor(None, container.start)
        return True

    async def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        client = self._get_client()
        loop = asyncio.get_event_loop()
        container = await loop.run_in_executor(None, lambda: client.containers.get(container_id))
        await loop.run_in_executor(None, lambda: container.stop(timeout=timeout))
        return True

    async def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        client = self._get_client()
        loop = asyncio.get_event_loop()
        container = await loop.run_in_executor(None, lambda: client.containers.get(container_id))
        await loop.run_in_executor(None, lambda: container.restart(timeout=timeout))
        return True

    async def delete_container(self, container_id: str, force: bool = False) -> bool:
        client = self._get_client()
        loop = asyncio.get_event_loop()
        container = await loop.run_in_executor(None, lambda: client.containers.get(container_id))
        await loop.run_in_executor(None, lambda: container.remove(force=force))
        return True

    async def stream_logs(self, container_id: str, follow: bool = True, tail: int = 100) -> AsyncIterator[LogEntry]:
        client = self._get_client()
        loop = asyncio.get_event_loop()
        container = await loop.run_in_executor(None, lambda: client.containers.get(container_id))
        
        log_stream = await loop.run_in_executor(None, lambda: container.logs(
            stream=follow, follow=follow, tail=tail, timestamps=True, stdout=True, stderr=True, demux=True
        ))

        def get_next():
            try:
                return next(log_stream, None)
            except StopIteration:
                return None

        while True:
            chunk = await loop.run_in_executor(None, get_next)
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
        client = self._get_client()
        loop = asyncio.get_event_loop()
        container = await loop.run_in_executor(None, lambda: client.containers.get(container_id))
        exit_code, output = await loop.run_in_executor(None, lambda: container.exec_run(cmd=command, stdout=True, stderr=True))
        return exit_code or 0, output or b""

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
