"""リモート MCP サーバーの接続・接続テスト API。"""

import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from ..models.remote import RemoteConnectResponse, RemoteTestResponse
from ..services.oauth import CredentialNotFoundError, RemoteServerNotFoundError
from ..services.remote_mcp import (
    EndpointNotAllowedError,
    RemoteMcpError,
    RemoteMcpService,
    TooManyConnectionsError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/remote-servers", tags=["remote-servers"])
remote_service = RemoteMcpService()


def _get_correlation_id(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None) or request.headers.get(
        "X-Correlation-ID"
    )


def _error_response(
    *, status_code: int, error_code: str, message: str, correlation_id: str | None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "message": message,
            "correlation_id": correlation_id,
        },
    )


@router.post("/{server_id}/connect", response_model=RemoteConnectResponse)
async def connect_remote_server(
    server_id: str, request: Request
) -> RemoteConnectResponse | JSONResponse:
    """SSE 接続を確立し capabilities を返す。"""
    correlation_id = _get_correlation_id(request)
    try:
        capabilities = await remote_service.connect(server_id)
        return RemoteConnectResponse(server_id=server_id, capabilities=capabilities)
    except EndpointNotAllowedError as exc:
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="endpoint_not_allowed",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except CredentialNotFoundError as exc:
        return _error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="credential_missing",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except RemoteServerNotFoundError as exc:
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="remote_server_not_found",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except TooManyConnectionsError as exc:
        return _error_response(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="too_many_connections",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except RemoteMcpError as exc:
        return _error_response(
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="remote_connect_failed",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("予期せぬエラーでリモート接続に失敗しました")
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="internal_error",
            message="リモートサーバーへの接続に失敗しました。",
            correlation_id=correlation_id,
        )


@router.post("/{server_id}/test", response_model=RemoteTestResponse)
async def test_remote_server(
    server_id: str, request: Request
) -> RemoteTestResponse | JSONResponse:
    """到達性と認証状態を検証する。"""
    correlation_id = _get_correlation_id(request)
    try:
        result = await remote_service.test_connection(server_id)
        return RemoteTestResponse(server_id=server_id, **result)
    except EndpointNotAllowedError as exc:
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="endpoint_not_allowed",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except CredentialNotFoundError as exc:
        return _error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="credential_missing",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except RemoteServerNotFoundError as exc:
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="remote_server_not_found",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except TooManyConnectionsError as exc:
        return _error_response(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="too_many_connections",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except RemoteMcpError as exc:
        return RemoteTestResponse(
            server_id=server_id,
            reachable=False,
            authenticated=False,
            error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("予期せぬエラーで接続テストに失敗しました")
        return RemoteTestResponse(
            server_id=server_id,
            reachable=False,
            authenticated=False,
            error="unexpected_error",
        )
