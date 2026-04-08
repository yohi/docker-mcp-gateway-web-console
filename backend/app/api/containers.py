"""Container API endpoints."""

import logging
import os
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from ..config import settings
from ..models.containers import (
    ContainerActionResponse,
    ContainerConfig,
    ContainerCreateResponse,
    ContainerListResponse,
)
from ..services.auth import AuthService
from ..services.base import ContainerProvider
from ..services.containers import (
    AuthenticationError,
    ContainerAlreadyExistsError,
    ContainerError,
    ContainerUnavailableError,
    ContainerService,
)
from ..services.docker_provider import DockerSdkProvider
from ..services.secrets import SecretManager
from ..services.state_store import StateStore
from .auth import get_auth_service, get_session_id
import docker.tls

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/containers", tags=["containers"])

# Singleton instances
_container_service: ContainerService = None
_secret_manager: SecretManager = None
_state_store: StateStore = None
_container_provider: ContainerProvider = None


def _docker_unavailable(e: ContainerUnavailableError) -> HTTPException:
    """Docker 接続不可時の共通レスポンスを生成する。"""
    detail: dict[str, object] = {
        "message": "Docker daemon is unavailable.",
        "remediation": "Docker デーモンを起動し、DOCKER_HOST またはソケットパスが正しいことを確認してください。",
    }
    safe_hosts = [host for host in e.attempted_hosts if not host.startswith("unix://")]
    if safe_hosts:
        detail["attempted_hosts"] = safe_hosts
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=detail,
    )


def get_secret_manager() -> SecretManager:
    """Dependency to get the secret manager instance."""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager


def get_container_provider() -> ContainerProvider:
    """Dependency to get the container provider instance."""
    global _container_provider
    if _container_provider is None:
        tls_config = None
        if settings.docker_tls_verify:
            # Resolve certificate paths, prioritizing explicit settings, 
            # then deriving from DOCKER_CERT_PATH if available.
            ca_cert = settings.docker_ca_cert
            client_cert = settings.docker_client_cert
            client_key = settings.docker_client_key
            
            if settings.docker_cert_path:
                if not ca_cert:
                    ca_cert = os.path.join(settings.docker_cert_path, "ca.pem")
                if not client_cert:
                    client_cert = os.path.join(settings.docker_cert_path, "cert.pem")
                if not client_key:
                    client_key = os.path.join(settings.docker_cert_path, "key.pem")

            tls_config = docker.tls.TLSConfig(
                client_cert=(client_cert, client_key) if client_cert and client_key else None,
                ca_cert=ca_cert,
                verify=True
            )
        
        # Currently only docker-sdk is supported, but can be extended
        _container_provider = DockerSdkProvider(
            base_url=settings.docker_host,
            tls_config=tls_config
        )
            
    return _container_provider


def get_container_service(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    secret_manager: Annotated[SecretManager, Depends(get_secret_manager)],
    container_provider: Annotated[ContainerProvider, Depends(get_container_provider)],
) -> ContainerService:
    """Dependency to get the container service instance."""
    global _container_service, _state_store
    if _container_service is None:
        _state_store = StateStore()
        _state_store.init_schema()
        _container_service = ContainerService(
            container_provider, 
            secret_manager, 
            auth_service,
            state_store=_state_store
        )
    else:
        # Update auth_service to handle dependency overrides in tests
        _container_service.auth_service = auth_service
        
    return _container_service


_last_docker_warn_message: str | None = None
_last_docker_warn_at: float | None = None


def _log_docker_unavailable(e: ContainerUnavailableError) -> None:
    """
    同一メッセージの連続 WARN スパムを抑制する (最終ログから60秒未満なら skip)。
    """
    global _last_docker_warn_message, _last_docker_warn_at
    now = time.monotonic()
    if (
        _last_docker_warn_message == str(e)
        and _last_docker_warn_at is not None
        and now - _last_docker_warn_at < 60
    ):
        return
    logger.warning("Docker unavailable while listing containers: %s", e)
    _last_docker_warn_message = str(e)
    _last_docker_warn_at = now


def _raise_container_http_exception(e: Exception) -> None:
    """Map Container exceptions to FastAPI HTTPExceptions."""
    if isinstance(e, AuthenticationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    if isinstance(e, ContainerAlreadyExistsError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    if isinstance(e, ContainerUnavailableError):
        raise _docker_unavailable(e) from e
    if isinstance(e, ContainerError):
        # Default to 400, but use 404 for specific "not found" messages
        status_code = status.HTTP_400_BAD_REQUEST
        if "not found" in str(e).lower() or "保存されていません" in str(e):
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=str(e),
        ) from e
    raise e


@router.get("", response_model=ContainerListResponse)
async def list_containers(
    session_id: Annotated[str, Depends(get_session_id)],
    container_service: Annotated[ContainerService, Depends(get_container_service)],
    all: bool = True,
):
    """
    List all Docker containers.
    
    Query parameters:
    - all: If true, include stopped containers. If false, only running containers.
    
    Requires valid session authentication.
    """
    try:
        containers = await container_service.list_containers_with_auth(session_id, all)
        return ContainerListResponse(containers=containers)
    except HTTPException:
        raise
    except AuthenticationError as e:
        _raise_container_http_exception(e)
    except ContainerUnavailableError as e:
        _log_docker_unavailable(e)
        return ContainerListResponse(
            containers=[],
            warning="Docker デーモンに接続できないため空の一覧を返しました。"
            " ホスト上で Docker が起動していることと、DOCKER_HOST/ソケットの権限を確認してください。",
        )
    except ContainerError as e:
        logger.error("Domain error listing containers: %s", e)
        return ContainerListResponse(
            containers=[],
            warning=f"コンテナ一覧の取得に失敗しました: {e}",
        )
    except Exception as e:
        logger.exception("Unexpected error listing containers")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while listing containers",
        ) from e


@router.post("", response_model=ContainerCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_container(
    config: ContainerConfig,
    session_id: Annotated[str, Depends(get_session_id)],
    container_service: Annotated[ContainerService, Depends(get_container_service)],
):
    """
    Create and start a new Docker container.
    
    This endpoint:
    1. Validates the session
    2. Resolves any Bitwarden references in environment variables
    3. Creates the Docker container
    4. Starts the container
    5. Returns the container ID
    
    Requires valid session authentication.
    """
    try:
        container_id = await container_service.create_container_with_auth(config, session_id)
        return ContainerCreateResponse(
            container_id=container_id,
            name=config.name,
            status="running",
        )
    except HTTPException:
        raise
    except (AuthenticationError, ContainerError) as e:
        _raise_container_http_exception(e)
    except Exception as e:
        logger.exception("Unexpected error creating container")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating container",
        ) from e


@router.get("/{container_id}/config", response_model=ContainerConfig)
async def get_container_config(
    container_id: str,
    session_id: Annotated[str, Depends(get_session_id)],
    container_service: Annotated[ContainerService, Depends(get_container_service)],
):
    """保存済みのコンテナ設定を取得する。"""
    try:
        config_data = await container_service.get_container_config_with_auth(
            container_id, session_id
        )
        return ContainerConfig.model_validate(config_data)
    except HTTPException:
        raise
    except (AuthenticationError, ContainerError) as e:
        _raise_container_http_exception(e)
    except Exception:
        logger.exception("Unexpected error getting container config")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve container config",
        )


@router.post("/install", response_model=ContainerCreateResponse, status_code=status.HTTP_201_CREATED)
async def install_container(
    config: ContainerConfig,
    session_id: Annotated[str, Depends(get_session_id)],
    container_service: Annotated[ContainerService, Depends(get_container_service)],
):
    """
    Install (create and start) a new Docker container.
    
    本エンドポイントはUIのインストールフロー用エイリアスで、`POST /containers` と同等の処理を行う。
    セッション検証後、環境変数のBitwarden参照解決を行い、コンテナを作成・起動してIDを返却する。
    """
    try:
        if not config.image:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="コンテナイメージが指定されていません",
            )
        container_id = await container_service.create_container_with_auth(config, session_id)
        return ContainerCreateResponse(
            container_id=container_id,
            name=config.name,
            status="running",
        )
    except HTTPException:
        raise
    except (AuthenticationError, ContainerError) as e:
        _raise_container_http_exception(e)
    except Exception as e:
        logger.exception("Unexpected error installing container")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating container",
        ) from e


@router.post("/{container_id}/start", response_model=ContainerActionResponse)
async def start_container(
    container_id: str,
    session_id: Annotated[str, Depends(get_session_id)],
    container_service: Annotated[ContainerService, Depends(get_container_service)],
):
    """
    Start a stopped container.
    
    Requires valid session authentication.
    """
    try:
        success = await container_service.start_container_with_auth(container_id, session_id)
        return ContainerActionResponse(
            success=success,
            message=f"Container {container_id} started successfully",
            container_id=container_id,
        )
    except HTTPException:
        raise
    except (AuthenticationError, ContainerError) as e:
        _raise_container_http_exception(e)
    except Exception as e:
        logger.error(f"Unexpected error starting container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while starting container"
        )


@router.post("/{container_id}/stop", response_model=ContainerActionResponse)
async def stop_container(
    container_id: str,
    session_id: Annotated[str, Depends(get_session_id)],
    container_service: Annotated[ContainerService, Depends(get_container_service)],
    timeout: int = 10,
):
    """
    Stop a running container.
    
    Query parameters:
    - timeout: Seconds to wait before killing the container (default: 10)
    
    Requires valid session authentication.
    """
    try:
        success = await container_service.stop_container_with_auth(
            container_id, session_id, timeout=timeout
        )
        return ContainerActionResponse(
            success=success,
            message=f"Container {container_id} stopped successfully",
            container_id=container_id,
        )
    except HTTPException:
        raise
    except (AuthenticationError, ContainerError) as e:
        _raise_container_http_exception(e)
    except Exception as e:
        logger.error(f"Unexpected error stopping container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while stopping container"
        )


@router.post("/{container_id}/restart", response_model=ContainerActionResponse)
async def restart_container(
    container_id: str,
    session_id: Annotated[str, Depends(get_session_id)],
    container_service: Annotated[ContainerService, Depends(get_container_service)],
    timeout: int = 10,
):
    """
    Restart a container.
    
    Query parameters:
    - timeout: Seconds to wait before killing the container during stop (default: 10)
    
    Requires valid session authentication.
    """
    try:
        success = await container_service.restart_container_with_auth(
            container_id, session_id, timeout=timeout
        )
        return ContainerActionResponse(
            success=success,
            message=f"Container {container_id} restarted successfully",
            container_id=container_id,
        )
    except HTTPException:
        raise
    except (AuthenticationError, ContainerError) as e:
        _raise_container_http_exception(e)
    except Exception as e:
        logger.error(f"Unexpected error restarting container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while restarting container"
        )


@router.delete("/{container_id}", response_model=ContainerActionResponse)
async def delete_container(
    container_id: str,
    session_id: Annotated[str, Depends(get_session_id)],
    container_service: Annotated[ContainerService, Depends(get_container_service)],
    force: bool = False,
):
    """
    Delete a container.
    
    Query parameters:
    - force: If true, force removal even if running (default: false)
    
    Requires valid session authentication.
    """
    try:
        success = await container_service.delete_container_with_auth(
            container_id, session_id, force=force
        )
        return ContainerActionResponse(
            success=success,
            message=f"Container {container_id} deleted successfully",
            container_id=container_id,
        )
    except HTTPException:
        raise
    except (AuthenticationError, ContainerError) as e:
        _raise_container_http_exception(e)
    except Exception as e:
        logger.error(f"Unexpected error deleting container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting container"
        )


@router.websocket("/{container_id}/logs")
async def stream_logs(
    websocket: WebSocket,
    container_id: str,
    container_service: Annotated[ContainerService, Depends(get_container_service)],
):
    """
    Stream container logs via WebSocket.
    
    The client should send the session_id as the first message after connecting.
    Then logs will be streamed in real-time.
    
    Message format:
    {
        "timestamp": "2024-01-01T12:00:00Z",
        "message": "log message",
        "stream": "stdout" | "stderr"
    }
    """
    await websocket.accept()
    
    try:
        # Wait for session_id from client
        session_data = await websocket.receive_json()
        session_id = session_data.get("session_id")
        
        if not session_id:
            await websocket.send_json({
                "error": "Missing session_id in first message"
            })
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Validate session
        # Use service to validate session for consistency
        is_valid = await container_service.auth_service.validate_session(session_id)
        if not is_valid:
            await websocket.send_json({
                "error": "Invalid or expired session"
            })
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Stream logs
        async for log_entry in container_service.stream_logs(container_id):
            await websocket.send_json({
                "timestamp": log_entry.timestamp.isoformat(),
                "message": log_entry.message,
                "stream": log_entry.stream,
            })
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for container {container_id}")
    except RuntimeError as e:
        logger.error(f"Error streaming logs: {e}")
        try:
            await websocket.send_json({"error": str(e)})
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception as send_exc:
            logger.debug(f"Failed to send error response: {send_exc}")
    except Exception as e:
        logger.error(f"Unexpected error in log streaming: {e}")
        try:
            await websocket.send_json({"error": "An unexpected error occurred"})
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception as send_exc:
            logger.debug(f"Failed to send error response: {send_exc}")
