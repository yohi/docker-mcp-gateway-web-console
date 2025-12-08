"""Container API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from ..models.containers import (
    ContainerActionResponse,
    ContainerConfig,
    ContainerCreateResponse,
    ContainerListResponse,
)
from ..services.auth import AuthService
from ..services.containers import ContainerService
from ..services.secrets import SecretManager
from .auth import get_auth_service, get_session_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/containers", tags=["containers"])

# Singleton instances
_container_service: ContainerService = None
_secret_manager: SecretManager = None


def get_secret_manager() -> SecretManager:
    """Dependency to get the secret manager instance."""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager


def get_container_service(
    secret_manager: Annotated[SecretManager, Depends(get_secret_manager)]
) -> ContainerService:
    """Dependency to get the container service instance."""
    global _container_service
    if _container_service is None:
        _container_service = ContainerService(secret_manager)
    return _container_service


@router.get("", response_model=ContainerListResponse)
async def list_containers(
    session_id: Annotated[str, Depends(get_session_id)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
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
        # Validate session
        is_valid = await auth_service.validate_session(session_id)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session"
            )
        
        # List containers
        containers = await container_service.list_containers(all_containers=all)
        
        return ContainerListResponse(containers=containers)
        
    except HTTPException:
        raise
    except RuntimeError as e:
        logger.error(f"Failed to list containers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error listing containers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while listing containers"
        )


async def _create_container_internal(
    config: ContainerConfig,
    session_id: str,
    auth_service: AuthService,
    container_service: ContainerService,
    operation_name: str = "create",
) -> ContainerCreateResponse:
    """コンテナ作成処理の共通内部ヘルパー。"""
    is_valid = await auth_service.validate_session(session_id)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    session = await auth_service.get_session(session_id)
    if session is None:
        logger.warning(
            f"Session {session_id} not found after validation ({operation_name})"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    container_id = await container_service.create_container(
        config=config,
        session_id=session_id,
        bw_session_key=session.bw_session_key,
    )

    return ContainerCreateResponse(
        container_id=container_id,
        name=config.name,
        status="running",
    )


@router.post("", response_model=ContainerCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_container(
    config: ContainerConfig,
    session_id: Annotated[str, Depends(get_session_id)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
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
        return await _create_container_internal(
            config, session_id, auth_service, container_service, "create"
        )
    except HTTPException:
        raise
    except RuntimeError as e:
        logger.exception(f"Failed to create container: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.exception(f"Unexpected error creating container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating container"
        ) from e


@router.post("/install", response_model=ContainerCreateResponse, status_code=status.HTTP_201_CREATED)
async def install_container(
    config: ContainerConfig,
    session_id: Annotated[str, Depends(get_session_id)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    container_service: Annotated[ContainerService, Depends(get_container_service)],
):
    """
    Install (create and start) a new Docker container.
    
    本エンドポイントはUIのインストールフロー用エイリアスで、`POST /containers` と同等の処理を行う。
    セッション検証後、環境変数のBitwarden参照解決を行い、コンテナを作成・起動してIDを返却する。
    """
    try:
        return await _create_container_internal(
            config, session_id, auth_service, container_service, "install"
        )
    except HTTPException:
        raise
    except RuntimeError as e:
        logger.exception(f"Failed to install container: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.exception(f"Unexpected error installing container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while installing container"
        ) from e


@router.post("/{container_id}/start", response_model=ContainerActionResponse)
async def start_container(
    container_id: str,
    session_id: Annotated[str, Depends(get_session_id)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    container_service: Annotated[ContainerService, Depends(get_container_service)],
):
    """
    Start a stopped container.
    
    Requires valid session authentication.
    """
    try:
        # Validate session
        is_valid = await auth_service.validate_session(session_id)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session"
            )
        
        # Start container
        success = await container_service.start_container(container_id)
        
        return ContainerActionResponse(
            success=success,
            message=f"Container {container_id} started successfully",
            container_id=container_id,
        )
        
    except HTTPException:
        raise
    except RuntimeError as e:
        logger.error(f"Failed to start container: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
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
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
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
        # Validate session
        is_valid = await auth_service.validate_session(session_id)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session"
            )
        
        # Stop container
        success = await container_service.stop_container(container_id, timeout=timeout)
        
        return ContainerActionResponse(
            success=success,
            message=f"Container {container_id} stopped successfully",
            container_id=container_id,
        )
        
    except HTTPException:
        raise
    except RuntimeError as e:
        logger.error(f"Failed to stop container: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
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
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
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
        # Validate session
        is_valid = await auth_service.validate_session(session_id)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session"
            )
        
        # Restart container
        success = await container_service.restart_container(container_id, timeout=timeout)
        
        return ContainerActionResponse(
            success=success,
            message=f"Container {container_id} restarted successfully",
            container_id=container_id,
        )
        
    except HTTPException:
        raise
    except RuntimeError as e:
        logger.error(f"Failed to restart container: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
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
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
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
        # Validate session
        is_valid = await auth_service.validate_session(session_id)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session"
            )
        
        # Delete container
        success = await container_service.delete_container(container_id, force=force)
        
        return ContainerActionResponse(
            success=success,
            message=f"Container {container_id} deleted successfully",
            container_id=container_id,
        )
        
    except HTTPException:
        raise
    except RuntimeError as e:
        logger.error(f"Failed to delete container: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
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
        auth_service = get_auth_service()
        is_valid = await auth_service.validate_session(session_id)
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
