"""リモート MCP サーバーの CRUD・接続 API。"""

import logging

import httpx
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from ..models.remote import (
    RemoteConnectResponse,
    RemoteServer,
    RemoteServerCreateRequest,
    RemoteServerEnableRequest,
    RemoteTestResponse,
)
from ..services.oauth import CredentialNotFoundError, RemoteServerNotFoundError
from ..services.remote_mcp import (
    CredentialExpiredError,
    DuplicateRemoteServerError,
    EndpointNotAllowedError,
    RemoteConnectionError,
    RemoteMcpError,
    RemoteMcpService,
    ServerDisabledError,
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


@router.get("", response_model=list[RemoteServer])
async def list_remote_servers() -> list[RemoteServer]:
    """登録済みリモートサーバーを一覧する。"""
    return await remote_service.list_servers()


@router.post("", response_model=RemoteServer, status_code=status.HTTP_201_CREATED)
async def register_remote_server(
    body: RemoteServerCreateRequest, request: Request
) -> RemoteServer | JSONResponse:
    """カタログ項目からリモートサーバーを登録する。"""
    correlation_id = _get_correlation_id(request)
    try:
        return await remote_service.register_server(
            catalog_item_id=body.catalog_item_id,
            name=body.name,
            endpoint=body.endpoint,
            correlation_id=correlation_id,
        )
    except EndpointNotAllowedError as exc:
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="endpoint_not_allowed",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except DuplicateRemoteServerError as exc:
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            error_code="remote_server_duplicate",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except RemoteMcpError as exc:
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="remote_server_error",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except Exception:
        logger.exception("予期せぬエラーでサーバー登録に失敗しました")
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="internal_error",
            message="リモートサーバーの登録に失敗しました。",
            correlation_id=correlation_id,
        )


@router.get("/{server_id}", response_model=RemoteServer)
async def get_remote_server(
    server_id: str, request: Request
) -> RemoteServer | JSONResponse:
    """server_id でリモートサーバーを取得する。"""
    correlation_id = _get_correlation_id(request)
    server = await remote_service.get_server(server_id)
    if server is None:
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="remote_server_not_found",
            message="指定されたリモートサーバーが見つかりません。",
            correlation_id=correlation_id,
        )
    return server


@router.post("/{server_id}/enable", response_model=RemoteServer)
async def enable_remote_server(
    server_id: str, body: RemoteServerEnableRequest, request: Request
) -> RemoteServer | JSONResponse:
    """サーバーを有効化する。"""
    correlation_id = _get_correlation_id(request)
    try:
        return await remote_service.enable_server(
            server_id,
            requires_auth=body.requires_auth,
            correlation_id=correlation_id,
        )
    except RemoteServerNotFoundError as exc:
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="remote_server_not_found",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except RemoteMcpError as exc:
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="remote_server_error",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except Exception:
        logger.exception("予期せぬエラーで有効化に失敗しました")
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="internal_error",
            message="リモートサーバーの有効化に失敗しました。",
            correlation_id=correlation_id,
        )


@router.post("/{server_id}/disable", response_model=RemoteServer)
async def disable_remote_server(
    server_id: str, request: Request
) -> RemoteServer | JSONResponse:
    """サーバーを無効化する。"""
    correlation_id = _get_correlation_id(request)
    try:
        return await remote_service.disable_server(
            server_id, correlation_id=correlation_id
        )
    except RemoteServerNotFoundError as exc:
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="remote_server_not_found",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except RemoteMcpError as exc:
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="remote_server_error",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except Exception:
        logger.exception("予期せぬエラーで無効化に失敗しました")
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="internal_error",
            message="リモートサーバーの無効化に失敗しました。",
            correlation_id=correlation_id,
        )


@router.delete(
    "/{server_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def delete_remote_server(
    server_id: str, request: Request, delete_credentials: bool = False
) -> Response:
    """サーバーを削除する。必要に応じて資格情報も削除する。"""
    correlation_id = _get_correlation_id(request)
    try:
        await remote_service.delete_server(
            server_id,
            delete_credentials=delete_credentials,
            correlation_id=correlation_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except RemoteServerNotFoundError as exc:
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="remote_server_not_found",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except RemoteMcpError as exc:
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="remote_server_error",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except Exception:
        logger.exception("予期せぬエラーで削除に失敗しました")
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="internal_error",
            message="リモートサーバーの削除に失敗しました。",
            correlation_id=correlation_id,
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
    except ServerDisabledError as exc:
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="server_disabled",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except CredentialExpiredError as exc:
        return _error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="credential_expired",
            message=str(exc),
            correlation_id=correlation_id,
        )
    except RemoteConnectionError as exc:
        return _error_response(
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="remote_connect_failed",
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
    except Exception:
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
    """接続テストを実行し、到達性と認証状態を返す。"""
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
    except CredentialExpiredError as exc:
        return _error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="credential_expired",
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
    except Exception:
        logger.exception("予期せぬエラーで接続テストに失敗しました")
        return RemoteTestResponse(
            server_id=server_id,
            reachable=False,
            authenticated=False,
            error="unexpected_error",
        )
