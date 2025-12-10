"""セッション生成とゲートウェイコンテナ起動を扱うサービス。"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import uuid4

from app.models.containers import ContainerConfig
from app.models.state import SessionRecord
from app.services.containers import ContainerError, ContainerService
from app.services.state_store import StateStore

logger = logging.getLogger(__name__)

# デフォルトのリソース制限・タイムアウト
DEFAULT_CPU_QUOTA = 0.5
DEFAULT_MEMORY_LIMIT = "512m"
DEFAULT_IDLE_MINUTES = 30


class SessionService:
    """セッション単位でゲートウェイコンテナを起動・保存する。"""

    def __init__(
        self,
        container_service: ContainerService,
        state_store: Optional[StateStore] = None,
    ) -> None:
        self.container_service = container_service
        self.state_store = state_store or StateStore()

    async def create_session(
        self,
        server_id: str,
        image: str,
        env: Optional[Dict[str, str]],
        bw_session_key: str,
        correlation_id: str,
        *,
        idle_minutes: int = DEFAULT_IDLE_MINUTES,
    ) -> SessionRecord:
        """
        セッション専用のゲートウェイコンテナを起動し、セッションレコードを保存する。

        - CPU 0.5core / メモリ 512MB を cgroup で制限
        - ネットワークは `none` で分離
        - on-failure 1 回の再起動ポリシーを付与
        - idle_deadline を idle_minutes 後に設定する
        """
        session_id = uuid4().hex
        labels = {
            "mcp.session_id": session_id,
            "mcp.server_id": server_id,
        }

        config = ContainerConfig(
            name=f"mcp-session-{session_id[:8]}",
            image=image,
            env=env or {},
            network_mode="none",
            labels=labels,
            cpus=DEFAULT_CPU_QUOTA,
            memory_limit=DEFAULT_MEMORY_LIMIT,
            restart_policy={"Name": "on-failure", "MaximumRetryCount": 1},
        )

        container_id = await self._create_with_retry(
            config=config,
            session_id=session_id,
            bw_session_key=bw_session_key,
            correlation_id=correlation_id,
        )

        idle_deadline = datetime.now(timezone.utc) + timedelta(minutes=idle_minutes)
        record = SessionRecord(
            session_id=session_id,
            server_id=server_id,
            config=config.model_dump(),
            state="running",
            idle_deadline=idle_deadline,
            gateway_endpoint=f"container://{container_id}",
            metrics_endpoint="",
            mtls_cert_ref=None,
            feature_flags={"cost_priority": False},
        )
        self.state_store.save_session(record)
        return record

    async def _create_with_retry(
        self,
        config: ContainerConfig,
        session_id: str,
        bw_session_key: str,
        correlation_id: str,
    ) -> str:
        """コンテナ作成を最大 2 回試行し、失敗時は例外を送出する。"""
        last_error: Optional[ContainerError] = None
        for attempt in range(2):
            try:
                return await self.container_service.create_container(
                    config=config,
                    session_id=session_id,
                    bw_session_key=bw_session_key,
                )
            except ContainerError as exc:  # pragma: no cover - 2 回目で捕捉
                last_error = exc
                logger.warning(
                    "Session container creation failed (attempt=%s, correlation_id=%s): %s",
                    attempt + 1,
                    correlation_id,
                    exc,
                )
                if attempt == 0:
                    continue
                raise

        # ここには到達しないはずだが mypy 向けに明示
        if last_error:
            raise last_error
        raise ContainerError("Unknown error while creating session container")
