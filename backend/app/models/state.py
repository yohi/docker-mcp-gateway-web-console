"""永続化ストアで利用するレコードモデル群。"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    """UTC 現在時刻を返す。"""
    return datetime.now(timezone.utc)


class CredentialRecord(BaseModel):
    """トークン資格情報の永続化レコード。"""

    credential_key: str
    token_ref: Dict[str, Any]
    scopes: List[str]
    expires_at: datetime
    server_id: str
    oauth_token_url: Optional[str] = None
    oauth_client_id: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=_now_utc)


class GitHubTokenRecord(BaseModel):
    """GitHub パーソナルアクセストークンの永続化レコード。"""

    token_ref: Dict[str, Any]
    source: str
    updated_by: str
    updated_at: datetime = Field(default_factory=_now_utc)


class AuthSessionRecord(BaseModel):
    """ログインセッションの永続化レコード。"""

    session_id: str
    user_email: str
    bw_session_key: str
    created_at: datetime = Field(default_factory=_now_utc)
    expires_at: datetime
    last_activity: datetime


class SessionRecord(BaseModel):
    """セッション状態の永続化レコード。"""

    session_id: str
    server_id: str
    config: Dict[str, Any]
    state: str
    idle_deadline: datetime
    gateway_endpoint: str
    metrics_endpoint: str
    mtls_cert_ref: Optional[Dict[str, Any]] = None
    feature_flags: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now_utc)


class JobRecord(BaseModel):
    """実行ジョブの永続化レコード。"""

    job_id: str
    session_id: str
    status: str
    queued_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    exit_code: Optional[int]
    timeout: bool
    truncated: bool
    output_ref: Optional[Dict[str, Any]]
    created_at: datetime = Field(default_factory=_now_utc)


class SignaturePolicyRecord(BaseModel):
    """署名検証ポリシーのレコード。"""

    server_id: str
    payload: Dict[str, Any]
    updated_at: datetime = Field(default_factory=_now_utc)


class GatewayAllowEntry(BaseModel):
    """外部ゲートウェイ許可リストのレコード。"""

    id: str
    type: str
    value: str
    created_by: str
    created_at: datetime = Field(default_factory=_now_utc)
    enabled: bool = True
    version: int = 1


class AuditLogEntry(BaseModel):
    """相関 ID 付き監査ログのレコード。"""

    id: Optional[int] = None
    correlation_id: str
    event_type: str
    metadata: Dict[str, Any]
    created_at: datetime = Field(default_factory=_now_utc)


class ContainerConfigRecord(BaseModel):
    """コンテナ設定の永続化レコード。"""

    container_id: str
    name: str
    image: str
    config: Dict[str, Any]
    created_at: datetime = Field(default_factory=_now_utc)
