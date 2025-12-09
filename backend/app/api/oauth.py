"""OAuth 関連 API エンドポイント。"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..models.oauth import (
    OAuthCallbackResponse,
    OAuthInitiateRequest,
    OAuthInitiateResponse,
)
from ..services.oauth import (
    OAuthError,
    OAuthProviderError,
    OAuthProviderUnavailableError,
    OAuthService,
    OAuthStateMismatchError,
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
            code_challenge=request.code_challenge,
            code_challenge_method=request.code_challenge_method,
        )
        return OAuthInitiateResponse(**result)
    except OAuthError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/callback", response_model=OAuthCallbackResponse)
async def oauth_callback(
    code: str = Query(..., description="認可コード"),
    state: str = Query(..., description="認可開始時の state"),
    server_id: str = Query(..., description="対象サーバーID"),
    code_verifier: str | None = Query(
        default=None, description="クライアント保持の PKCE code_verifier"
    ),
) -> JSONResponse | OAuthCallbackResponse:
    """認可コードをトークンに交換する。"""
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
            content={"message": str(exc)},
        )
    except OAuthProviderError as exc:
        return JSONResponse(
            status_code=400,
            content={"message": str(exc)},
        )
    except OAuthProviderUnavailableError as exc:
        return JSONResponse(
            status_code=502,
            content={"message": str(exc)},
        )
    except OAuthError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
