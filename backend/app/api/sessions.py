"""セッション作成 API エンドポイント。"""

import logging
from functools import lru_cache
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth import get_auth_service, get_session_id
from app.api.containers import get_container_service, get_secret_manager
from app.models.sessions import SessionCreateRequest, SessionCreateResponse
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
