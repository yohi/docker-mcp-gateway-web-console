"""GitHub トークン取得・保存 API エンドポイント。"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..models.github_token import (
    GitHubTokenDeleteResponse,
    GitHubTokenSaveRequest,
    GitHubTokenSaveResponse,
    GitHubTokenSearchResponse,
    GitHubTokenStatus,
)
from ..services.auth import AuthError, AuthService
from ..services.github_token import GitHubTokenError, GitHubTokenService
from ..services.secrets import SecretManager
from .auth import get_auth_service, get_session_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/github-token", tags=["github-token"])

_github_token_service: GitHubTokenService | None = None
_secret_manager: SecretManager | None = None


def get_secret_manager() -> SecretManager:
    """SecretManager のシングルトンを返す。"""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager


def get_github_token_service(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    secret_manager: Annotated[SecretManager, Depends(get_secret_manager)],
) -> GitHubTokenService:
    """GitHubTokenService のシングルトンを返す。"""
    global _github_token_service
    if _github_token_service is None:
        _github_token_service = GitHubTokenService(
            secret_manager=secret_manager,
            auth_service=auth_service,
        )
    return _github_token_service


@router.get("/status", response_model=GitHubTokenStatus)
async def get_status(
    github_token_service: Annotated[GitHubTokenService, Depends(get_github_token_service)],
) -> GitHubTokenStatus:
    """保存済み GitHub トークンの状態を返す。"""
    return github_token_service.get_status()


@router.get("/search", response_model=GitHubTokenSearchResponse)
async def search_items(
    query: str = Query(..., description="Bitwarden の検索キーワード（必須）"),
    limit: int = Query(20, ge=1, le=100, description="最大取得件数"),
    session_id: Annotated[str, Depends(get_session_id)] = "",
    github_token_service: Annotated[GitHubTokenService, Depends(get_github_token_service)] = None,
) -> GitHubTokenSearchResponse:
    """Bitwarden アイテムを検索し、ID/フィールド候補を返す。"""
    try:
        items = await github_token_service.search_items(query, session_id=session_id, limit=limit)
        return GitHubTokenSearchResponse(items=items)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except GitHubTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Unexpected error while searching Bitwarden items: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bitwarden 検索中に予期しないエラーが発生しました",
        ) from exc


@router.post("", response_model=GitHubTokenSaveResponse)
async def save_github_token(
    request: GitHubTokenSaveRequest,
    session_id: Annotated[str, Depends(get_session_id)],
    github_token_service: Annotated[GitHubTokenService, Depends(get_github_token_service)],
) -> GitHubTokenSaveResponse:
    """Bitwarden から GitHub トークンを取得して保存する。"""
    try:
        status_result = await github_token_service.save_from_bitwarden(
            session_id=session_id, item_id=request.item_id, field=request.field
        )
        return GitHubTokenSaveResponse(success=True, status=status_result)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except GitHubTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Unexpected error while saving GitHub token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub トークン保存中に予期しないエラーが発生しました",
        ) from exc


@router.delete("", response_model=GitHubTokenDeleteResponse)
async def delete_github_token(
    session_id: Annotated[str, Depends(get_session_id)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    github_token_service: Annotated[GitHubTokenService, Depends(get_github_token_service)],
) -> GitHubTokenDeleteResponse:
    """保存済み GitHub トークンを削除する。"""
    try:
        is_valid = await auth_service.validate_session(session_id)
        if not is_valid:
            raise AuthError("セッションが無効または期限切れです")
        github_token_service.delete_token()
        return GitHubTokenDeleteResponse(success=True)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except GitHubTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error while deleting GitHub token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub トークン削除中に予期しないエラーが発生しました",
        ) from exc
