"""セッション作成・設定更新・実行管理の API エンドポイント。"""

import logging
from functools import lru_cache
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth import get_auth_service, get_session_id
from app.api.containers import get_container_service, get_secret_manager
from app.models.sessions import (
    SessionConfigResponse,
    SessionConfigUpdateRequest,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionExecAsyncResponse,
    SessionExecRequest,
    SessionExecSyncResponse,
    SessionJobStatusResponse,
)
from app.models.state import JobRecord
from app.services.auth import AuthService
from app.services.sessions import SessionService
from app.services.state_store import StateStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@lru_cache(maxsize=1)
def get_session_service() -> SessionService:
    """SessionService のシングルトンを返す。"""
    state_store = StateStore()
    container_service = get_container_service(secret_manager=get_secret_manager())
    return SessionService(
        container_service=container_service,
        state_store=state_store,
    )


@router.post("", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreateRequest,
    session_id: Annotated[str, Depends(get_session_id)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionCreateResponse:
    """
    セッション専用のゲートウェイコンテナを起動する。

    - セッション検証後に CPU 0.5core / メモリ 512MB 制限でコンテナを起動
    - ネットワークは `none` で分離
    - on-failure 1 回の再起動ポリシーを設定
    """
    is_valid = await auth_service.validate_session(session_id)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    session = await auth_service.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    record = await session_service.create_session(
        server_id=payload.server_id,
        image=payload.image,
        env=payload.env,
        bw_session_key=session.bw_session_key,
        correlation_id=session_id,
        idle_minutes=payload.idle_minutes,
    )

    parsed_endpoint = urlparse(record.gateway_endpoint)
    if not parsed_endpoint.scheme or not (parsed_endpoint.netloc or parsed_endpoint.path):
        logger.error("Invalid gateway endpoint format: %s", record.gateway_endpoint)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid gateway endpoint format",
        )

    container_id = parsed_endpoint.netloc or parsed_endpoint.path.lstrip("/")
    if not container_id:
        logger.error("Failed to derive container_id from gateway endpoint: %s", record.gateway_endpoint)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to derive container id",
        )
    return SessionCreateResponse(
        session_id=record.session_id,
        container_id=container_id,
        gateway_endpoint=record.gateway_endpoint,
        metrics_endpoint=record.metrics_endpoint,
        idle_deadline=record.idle_deadline,
    )


@router.patch("/{target_session_id}/config", response_model=SessionConfigResponse)
async def update_session_config(
    target_session_id: str,
    payload: SessionConfigUpdateRequest,
    session_id: Annotated[str, Depends(get_session_id)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionConfigResponse:
    """実行系設定を更新し、永続化して返す。"""
    is_valid = await auth_service.validate_session(session_id)
    if not is_valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    record = await session_service.update_session_config(
        session_id=target_session_id,
        max_run_seconds=payload.max_run_seconds,
        output_bytes_limit=payload.output_bytes_limit,
    )

    runtime = record.config.get("runtime", {})
    return SessionConfigResponse(session_id=record.session_id, runtime=runtime)


@router.post(
    "/{target_session_id}/exec",
    response_model=SessionExecSyncResponse | SessionExecAsyncResponse,
)
async def execute_session_command(
    target_session_id: str,
    payload: SessionExecRequest,
    session_id: Annotated[str, Depends(get_session_id)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionExecSyncResponse | SessionExecAsyncResponse:
    """mcp-exec 相当のコマンドを実行する。"""
    session = await auth_service.get_session(session_id)
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    result = await session_service.execute_command(
        session_id=target_session_id,
        tool=payload.tool,
        args=payload.args,
        async_mode=payload.async_mode,
        max_run_seconds=payload.max_run_seconds,
        output_bytes_limit=payload.output_bytes_limit,
    )

    if isinstance(result, JobRecord):
        return SessionExecAsyncResponse(
            job_id=result.job_id,
            status=result.status,
            queued_at=result.queued_at,
            started_at=result.started_at,
            result_url=None,
        )

    return SessionExecSyncResponse(
        output=result.output,
        exit_code=result.exit_code,
        timeout=result.timeout,
        truncated=result.truncated,
        started_at=result.started_at,
        finished_at=result.finished_at,
    )


@router.get("/{target_session_id}/jobs/{job_id}", response_model=SessionJobStatusResponse)
async def get_job_status(
    target_session_id: str,
    job_id: str,
    session_id: Annotated[str, Depends(get_session_id)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionJobStatusResponse:
    """非同期ジョブの状態を返す。"""
    is_valid = await auth_service.validate_session(session_id)
    if not is_valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    job = session_service.state_store.get_job(job_id)
    if job is None or job.session_id != target_session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")

    status_obj = await session_service.get_job_status(job_id)
    if status_obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")

    return SessionJobStatusResponse(
        job_id=status_obj.job_id,
        status=status_obj.status,
        output=status_obj.output,
        exit_code=status_obj.exit_code,
        timeout=status_obj.timeout,
        truncated=status_obj.truncated,
        started_at=status_obj.started_at,
        finished_at=status_obj.finished_at,
    )
