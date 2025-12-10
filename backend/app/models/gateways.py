"""外部ゲートウェイ関連の Pydantic モデル。"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class GatewayAllowOverride(BaseModel):
    """リクエストで指定する許可リストの上書き項目。"""

    id: str = Field(..., description="許可リスト ID")
    type: Literal["domain", "pattern", "service"] = Field(
        ..., description="照合タイプ（ドメイン/パターン/サービス）"
    )
    value: str = Field(..., description="許可値（ドメイン/パターン/サービス名）")
    enabled: bool = Field(default=True, description="有効かどうか")
    version: int = Field(default=1, description="バージョン（大きい方を優先）")


class GatewayHealthPayload(BaseModel):
    """ヘルスチェック結果のレスポンスペイロード。"""

    status: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    last_error: Optional[str] = None


class GatewayRegistrationRequest(BaseModel):
    """外部ゲートウェイ登録のリクエストボディ。"""

    url: HttpUrl = Field(..., description="外部ゲートウェイのベース URL")
    token: str = Field(..., min_length=1, description="認証用トークン")
    type: str = Field(default="external", description="ゲートウェイ種別")
    allowlist_overrides: List[GatewayAllowOverride] = Field(
        default_factory=list, description="組織別の許可リスト上書き"
    )


class GatewayRegistrationResponse(BaseModel):
    """登録結果のレスポンス。"""

    gateway_id: str
    status: str
    external_mode_enabled: bool
    health: GatewayHealthPayload


class GatewayHealthResponse(BaseModel):
    """手動ヘルスチェックのレスポンス。"""

    gateway_id: str
    status: str
    health: GatewayHealthPayload
