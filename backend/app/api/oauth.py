"""OAuth 関連 API エンドポイント。"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ..models.oauth import (
    OAuthCallbackResponse,
    OAuthInitiateRequest,
    OAuthInitiateResponse,
    OAuthRefreshRequest,
    OAuthRefreshResponse,
)
from ..services.oauth import (
    CredentialNotFoundError,
    OAuthError,
    OAuthInvalidGrantError,
    OAuthProviderError,
    OAuthProviderUnavailableError,
    OAuthService,
    OAuthStateMismatchError,
    ScopeNotAllowedError,
)

router = APIRouter(prefix="/api/catalog/oauth", tags=["oauth"])
oauth_service = OAuthService()


@router.post("/initiate", response_model=OAuthInitiateResponse)
async def initiate_oauth(request: OAuthInitiateRequest) -> OAuthInitiateResponse:
    """state と PKCE を生成し、認可 URL を返却する。"""
    try:
        result = oauth_service.start_auth(
            server_id=request.server_id,
            scopes=request.scopes,
            authorize_url=request.authorize_url,
            token_url=request.token_url,
            client_id=request.client_id,
            redirect_uri=request.redirect_uri,
            code_challenge=request.code_challenge,
            code_challenge_method=request.code_challenge_method,
        )
        return OAuthInitiateResponse(**result)
    except ScopeNotAllowedError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": str(exc), "missing_scopes": exc.missing},
        ) from exc
    except OAuthError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/callback", response_model=OAuthCallbackResponse)
async def oauth_callback(
    request: Request,
    code: str = Query(..., description="認可コード"),
    state: str = Query(..., description="認可開始時の state"),
    server_id: str | None = Query(default=None, description="対象サーバーID"),
    code_verifier: str | None = Query(
        default=None, description="クライアント保持の PKCE code_verifier"
    ),
) -> JSONResponse | OAuthCallbackResponse:
    """認可コードをトークンに交換する。"""
    correlation_id = getattr(request.state, "correlation_id", None) or request.headers.get(
        "X-Correlation-ID"
    )
    try:
        result = await oauth_service.exchange_token(
            code=code,
            state=state,
            server_id=server_id,
            code_verifier=code_verifier,
        )
        return OAuthCallbackResponse(**result)
    except OAuthStateMismatchError as exc:
        return JSONResponse(
            status_code=401,
            content={
                "error_code": "state_mismatch",
                "message": str(exc),
                "remediation": "認可フローを最初からやり直してください",
                "correlation_id": correlation_id,
            },
        )
    except OAuthProviderError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "provider_error",
                "message": str(exc),
                "correlation_id": correlation_id,
            },
        )
    except OAuthProviderUnavailableError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error_code": "provider_unavailable",
                "message": str(exc),
                "correlation_id": correlation_id,
            },
        )
    except OAuthError as exc:
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "internal_error",
                "message": str(exc),
                "correlation_id": correlation_id,
            },
        )


@router.post("/refresh", response_model=OAuthRefreshResponse)
async def oauth_refresh(
    request: Request, oauth_request: OAuthRefreshRequest
) -> JSONResponse | OAuthRefreshResponse:
    """credential_key に紐づくトークンをリフレッシュする。"""
    correlation_id = getattr(request.state, "correlation_id", None) or request.headers.get(
        "X-Correlation-ID"
    )
    def error_response(
        *,
        status_code: int,
        error_code: str,
        message: str,
        remediation: str | None = None,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={
                "error_code": error_code,
                "message": message,
                "remediation": remediation,
                "correlation_id": correlation_id,
            },
        )

    try:
        result = await oauth_service.refresh_token(
            server_id=oauth_request.server_id,
            credential_key=oauth_request.credential_key,
        )
        return OAuthRefreshResponse(**result)
    except OAuthInvalidGrantError as exc:
        return error_response(
            status_code=401,
            error_code="provider_error",
            message=str(exc),
            remediation=None,
        )
    except OAuthProviderUnavailableError as exc:
        return error_response(
            status_code=503,
            error_code="provider_unavailable",
            message=str(exc),
            remediation=None,
        )
    except CredentialNotFoundError as exc:
        return error_response(
            status_code=404,
            error_code="internal_error",
            message=str(exc),
            remediation=None,
        )
    except OAuthError as exc:
        return error_response(
            status_code=422,
            error_code="internal_error",
            message=str(exc),
            remediation=None,
        )
