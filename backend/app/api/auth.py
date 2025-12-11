"""Authentication API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Header, status

from ..models.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    SessionValidationResponse,
)
from ..services.auth import AuthError, AuthService
from ..services.state_store import StateStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Singleton auth service instance
_auth_service: AuthService = None


def get_auth_service() -> AuthService:
    """Dependency to get the auth service instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService(state_store=StateStore())
    return _auth_service


async def get_session_id(
    authorization: Annotated[str | None, Header()] = None,
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
) -> str:
    """
    Extract session ID from Authorization header.
    
    Expected format: "Bearer <session_id>"
    互換性のために X-Session-ID ヘッダーも受け付ける。
    """
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected: Bearer <session_id>"
        )

    if x_session_id:
        return x_session_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authorization header"
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    login_request: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    """
    Authenticate user with Bitwarden and create a session.
    
    Supports two authentication methods:
    - API key: Requires email and api_key
    - Master password: Requires email and master_password
    """
    try:
        session = await auth_service.login(login_request)
        
        return LoginResponse(
            session_id=session.session_id,
            expires_at=session.expires_at,
            user_email=session.user_email,
            created_at=session.created_at
        )
        
    except AuthError as e:
        logger.warning(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during authentication"
        )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    session_id: Annotated[str, Depends(get_session_id)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    """
    Terminate a session and revoke vault access.
    
    Requires Authorization header with Bearer token (session_id).
    """
    try:
        success = await auth_service.logout(session_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        return LogoutResponse(success=True)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during logout"
        )


@router.get("/session", response_model=SessionValidationResponse)
async def validate_session(
    session_id: Annotated[str, Depends(get_session_id)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    """
    Check if a session is valid and not expired.
    
    Requires Authorization header with Bearer token (session_id).
    """
    try:
        is_valid = await auth_service.validate_session(session_id)
        
        if is_valid:
            session = await auth_service.get_session(session_id)
            return SessionValidationResponse(
                valid=True,
                session_id=session.session_id if session else None,
                user_email=session.user_email if session else None,
                created_at=session.created_at if session else None,
                expires_at=session.expires_at
            ) if session else SessionValidationResponse(valid=False)
        else:
            return SessionValidationResponse(valid=False)
            
    except Exception as e:
        logger.error(f"Unexpected error during session validation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during session validation"
        )
