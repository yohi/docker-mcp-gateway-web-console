"""OAuth 関連モデル。"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class OAuthInitiateRequest(BaseModel):
    """認可開始リクエスト。

    Note: authorize_url, token_url, redirect_uri は HttpUrl 型でバリデーションされます。
    不正なURL形式の場合は422エラーを返します。HTTP/HTTPSスキームのみ許可されます。
    """

    server_id: str = Field(..., description="対象サーバーID")
    scopes: List[str] = Field(default_factory=list, description="要求スコープ")
    authorize_url: Optional[HttpUrl] = Field(
        default=None, description="OAuth authorize endpoint URL (override, HTTP/HTTPS required)"
    )
    token_url: Optional[HttpUrl] = Field(
        default=None, description="OAuth token endpoint URL (override, HTTP/HTTPS required)"
    )
    client_id: Optional[str] = Field(
        default=None, description="OAuth client_id (override)"
    )
    redirect_uri: Optional[HttpUrl] = Field(
        default=None, description="OAuth redirect_uri (override, HTTP/HTTPS required)"
    )
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
    credential_key: Optional[str] = Field(
        default=None, description="保存された資格情報の参照キー"
    )
    expires_at: Optional[datetime] = Field(
        default=None, description="アクセストークンの有効期限（UTC）"
    )


class OAuthRefreshRequest(BaseModel):
    """トークンリフレッシュリクエスト。"""

    server_id: str = Field(..., description="対象サーバーID")
    credential_key: str = Field(..., description="リフレッシュ対象の credential_key")


class OAuthRefreshResponse(BaseModel):
    """トークンリフレッシュレスポンス。"""

    credential_key: str = Field(..., description="新しい credential_key")
    refreshed: bool = Field(..., description="リフレッシュが実行されたか")
    scope: List[str] = Field(default_factory=list, description="付与されたスコープ")
    expires_at: datetime = Field(..., description="アクセストークンの有効期限（UTC）")
