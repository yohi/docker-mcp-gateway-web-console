"""外部/E2B ゲートウェイの登録・ヘルスチェック API。"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from ..models.gateways import (
    GatewayHealthResponse,
    GatewayRegistrationRequest,
    GatewayRegistrationResponse,
)
from ..services.gateways import AllowlistError, GatewayError, GatewayService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gateways", tags=["gateways"])
gateway_service = GatewayService()


@router.post("", response_model=GatewayRegistrationResponse)
async def register_gateway(
    request: GatewayRegistrationRequest,
    correlation_id: Optional[str] = None,
) -> GatewayRegistrationResponse:
    """外部ゲートウェイを保存し直後にヘルスチェックを実行する。"""
    try:
        record = await gateway_service.register_gateway(request, correlation_id=correlation_id)
        health = record.last_health
        if health is None:
            raise GatewayError("ヘルスチェック結果が取得できませんでした。")
        status_text = health.status
        external_mode_enabled = health.status == "healthy"
        return GatewayRegistrationResponse(
            gateway_id=record.gateway_id,
            status=status_text,
            external_mode_enabled=external_mode_enabled,
            health=health,
        )
    except AllowlistError as exc:
        logger.warning("許可リスト検証に失敗: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except GatewayError as exc:
        logger.exception("ゲートウェイ登録に失敗")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("予期せぬエラーでゲートウェイ登録に失敗")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="外部ゲートウェイの登録に失敗しました。",
        ) from exc


@router.get("/{gateway_id}/health", response_model=GatewayHealthResponse)
async def manual_healthcheck(gateway_id: str) -> GatewayHealthResponse:
    """登録済みゲートウェイの手動ヘルスチェックを実行する。"""
    try:
        record = await gateway_service.healthcheck(gateway_id)
        if record.last_health is None:
            raise GatewayError("ヘルスチェック結果が取得できませんでした。")
        return GatewayHealthResponse(
            gateway_id=gateway_id, status=record.last_health.status, health=record.last_health
        )
    except GatewayError as exc:
        logger.warning("ヘルスチェック失敗: %s", exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("予期せぬエラーでヘルスチェックに失敗")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ヘルスチェックに失敗しました。",
        ) from exc
