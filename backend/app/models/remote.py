"""リモート MCP サーバーのモデル定義。"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    """UTC 現在時刻を返す。"""
    return datetime.now(timezone.utc)


class RemoteServerStatus(str, Enum):
    """リモートサーバーの状態を表す列挙。"""

    UNREGISTERED = "unregistered"
    REGISTERED = "registered"
    AUTH_REQUIRED = "auth_required"
    AUTHENTICATED = "authenticated"
    DISABLED = "disabled"
    ERROR = "error"


class RemoteServer(BaseModel):
    """リモート MCP サーバーのドメインモデル。"""

    server_id: str
    catalog_item_id: str
    name: str
    endpoint: str
    status: RemoteServerStatus = Field(default=RemoteServerStatus.REGISTERED)
    credential_key: Optional[str] = None
    last_connected_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=_now_utc)
