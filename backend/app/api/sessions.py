"""セッション作成 API エンドポイント。"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth import get_auth_service, get_session_id
from app.api.containers import get_container_service
from app.models.sessions import SessionCreateRequest, SessionCreateResponse
from app.services.auth import AuthService
from app.services.containers import ContainerService
from app.services.sessions import SessionService
from app.services.state_store import StateStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

_session_service: SessionService | None = None
_state_store: StateStore | None = None


def get_session_service(
    container_service: Annotated[ContainerService, Depends(get_container_service)],
) -> SessionService:
    """SessionService のシングルトンを返す。"""
    global _session_service, _state_store
    if _state_store is None:
        _state_store = StateStore()
    if _session_service is None:
        _session_service = SessionService(
            container_service=container_service,
            state_store=_state_store,
        )
    return _session_service


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

    container_id = record.gateway_endpoint.split("://", maxsplit=1)[-1]
    return SessionCreateResponse(
        session_id=record.session_id,
        container_id=container_id,
        gateway_endpoint=record.gateway_endpoint,
        metrics_endpoint=record.metrics_endpoint,
        idle_deadline=record.idle_deadline,
    )
