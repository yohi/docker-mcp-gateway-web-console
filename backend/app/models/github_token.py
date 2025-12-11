"""GitHub トークン管理用のAPIモデル。"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class GitHubTokenStatus(BaseModel):
    """保存済み GitHub トークンの状態。"""

    configured: bool = Field(description="トークンが保存されているか")
    source: Optional[str] = Field(
        default=None, description="取得元（例: bitwarden:item-id:field）"
    )
    updated_by: Optional[str] = Field(default=None, description="最終更新者")
    updated_at: Optional[datetime] = Field(default=None, description="最終更新日時")


class GitHubTokenSaveRequest(BaseModel):
    """Bitwarden から GitHub トークンを取得するためのリクエスト。"""

    item_id: str = Field(description="Bitwarden アイテム ID")
    field: str = Field(description="取得するフィールド名（例: password）")


class GitHubTokenSaveResponse(BaseModel):
    """トークン保存結果のレスポンス。"""

    success: bool
    status: GitHubTokenStatus


class GitHubItemSummary(BaseModel):
    """Bitwarden アイテムの概要。"""

    id: str
    name: str
    fields: List[str] = Field(default_factory=list, description="選択可能なフィールド名一覧")
    type: Optional[str] = Field(default=None, description="アイテムタイプ")


class GitHubTokenSearchResponse(BaseModel):
    """検索結果レスポンス。"""

    items: List[GitHubItemSummary]


class GitHubTokenDeleteResponse(BaseModel):
    """削除結果レスポンス。"""

    success: bool

