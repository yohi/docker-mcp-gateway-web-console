"""セッション関連の API モデル。"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    """セッション作成リクエスト。"""

    server_id: str = Field(..., description="対象となるカタログサーバー ID")
    image: str = Field(..., description="起動する Docker イメージ")
    image_digest: Optional[str] = Field(
        default=None, description="イメージの sha256 ダイジェスト（任意）"
    )
    image_thumbprint: Optional[str] = Field(
        default=None, description="イメージ署名証明書のサムプリント（任意）"
    )
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


class SessionConfigUpdateRequest(BaseModel):
    """実行系設定の更新リクエスト。"""

    max_run_seconds: Optional[int] = Field(
        default=None,
        ge=10,
        le=300,
        description="コマンドの最大実行秒数 (10〜300)。",
    )
    output_bytes_limit: Optional[int] = Field(
        default=None,
        ge=32_000,
        le=1_000_000,
        description="stdout/stderr 合算の最大バイト数 (32KB〜1MB)。",
    )


class SessionConfigResponse(BaseModel):
    """実行系設定のレスポンス。"""

    session_id: str = Field(..., description="対象セッション ID")
    runtime: Dict[str, int] = Field(..., description="実行パラメータ")


class SessionExecRequest(BaseModel):
    """mcp-exec リクエスト。"""

    tool: str = Field(..., description="実行するツール名")
    args: List[str] = Field(default_factory=list, description="ツールへの引数")
    async_mode: bool = Field(
        default=False, description="非同期ジョブとして実行する場合は True"
    )
    max_run_seconds: Optional[int] = Field(
        default=None,
        ge=10,
        le=300,
        description="上書き用の最大実行秒数",
    )
    output_bytes_limit: Optional[int] = Field(
        default=None,
        ge=32_000,
        le=1_000_000,
        description="上書き用の出力バイト上限",
    )


class SessionExecSyncResponse(BaseModel):
    """同期実行結果。"""

    output: str = Field(..., description="出力（切り詰め後）")
    exit_code: int = Field(..., description="終了コード")
    timeout: bool = Field(..., description="タイムアウトした場合 True")
    truncated: bool = Field(..., description="出力が切り詰められた場合 True")
    started_at: datetime = Field(..., description="開始時刻")
    finished_at: datetime = Field(..., description="終了時刻")


class SessionExecAsyncResponse(BaseModel):
    """非同期ジョブの作成結果。"""

    job_id: str = Field(..., description="ジョブ ID")
    status: str = Field(..., description="ジョブステータス")
    queued_at: datetime = Field(..., description="キュー投入時刻")
    started_at: Optional[datetime] = Field(
        default=None, description="開始時刻 (未開始の場合は null)"
    )
    result_url: Optional[str] = Field(
        default=None, description="結果取得 URL (将来拡張用)"
    )


class SessionJobStatusResponse(BaseModel):
    """ジョブの現在状態。"""

    job_id: str = Field(..., description="ジョブ ID")
    status: str = Field(..., description="ジョブステータス")
    output: Optional[str] = Field(default=None, description="出力（完了時のみ）")
    exit_code: Optional[int] = Field(default=None, description="終了コード")
    timeout: bool = Field(..., description="タイムアウトした場合 True")
    truncated: bool = Field(..., description="出力が切り詰められた場合 True")
    started_at: Optional[datetime] = Field(default=None, description="開始時刻")
    finished_at: Optional[datetime] = Field(default=None, description="終了時刻")
