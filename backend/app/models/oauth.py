"""OAuth 関連モデル。"""

from typing import List, Optional

from pydantic import BaseModel, Field


class OAuthInitiateRequest(BaseModel):
    """認可開始リクエスト。"""

    server_id: str = Field(..., description="対象サーバーID")
    scopes: List[str] = Field(default_factory=list, description="要求スコープ")
    code_challenge: Optional[str] = Field(
        default=None,
        description="クライアント生成の PKCE code_challenge",
    )
    code_challenge_method: str = Field(
        default="S256",
        description="PKCE code_challenge_method (例: S256/plain)",
    )


class OAuthInitiateResponse(BaseModel):
    """認可開始レスポンス。"""

    auth_url: str = Field(..., description="リダイレクト先認可URL")
    state: str = Field(..., description="CSRF 防止用 state")
    required_scopes: List[str] = Field(default_factory=list, description="要求スコープ")


class OAuthCallbackResponse(BaseModel):
    """認可コールバックレスポンス。"""

    status: str = Field(..., description="認可状態")
    scope: List[str] = Field(default_factory=list, description="認可されたスコープ")
    expires_in: Optional[int] = Field(default=None, description="アクセストークン有効秒数")
