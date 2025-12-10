"""セッション関連の API モデル。"""

from datetime import datetime
from typing import Dict

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    """セッション作成リクエスト。"""

    server_id: str = Field(..., description="対象となるカタログサーバー ID")
    image: str = Field(..., description="起動する Docker イメージ")
    env: Dict[str, str] = Field(
        default_factory=dict, description="環境変数（Bitwarden 参照を含むことがある）"
    )
    idle_minutes: int = Field(
        default=30,
        ge=1,
        le=240,
        description="アイドルタイムアウト（分）。既定は 30 分。",
    )


class SessionCreateResponse(BaseModel):
    """セッション作成レスポンス。"""

    session_id: str = Field(..., description="生成されたセッション ID")
    container_id: str = Field(..., description="起動したコンテナ ID")
    gateway_endpoint: str = Field(..., description="ゲートウェイ接続先")
    metrics_endpoint: str = Field(..., description="メトリクスエンドポイント")
    idle_deadline: datetime = Field(..., description="アイドル期限 (ISO8601)")
