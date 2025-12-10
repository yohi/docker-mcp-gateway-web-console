"""SessionService のセッション作成動作を検証するテスト。"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from unittest.mock import AsyncMock

import pytest

from app.models.state import SessionRecord
from app.services.containers import ContainerError
from app.services.sessions import SessionService


class _DummyStateStore:
    """永続化ストアの代替実装（メモリ保持のみ）。"""

    def __init__(self) -> None:
        self.saved: List[SessionRecord] = []

    def save_session(self, record: SessionRecord) -> None:
        self.saved.append(record)

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        for record in self.saved:
            if record.session_id == session_id:
                return record
        return None


@pytest.mark.asyncio
async def test_create_session_applies_isolation_and_limits() -> None:
    """
    セッション作成時にネットワーク分離と cgroup 制限が付与され、
    idle_deadline が 30 分先に設定されることを検証する。
    """
    container_service = AsyncMock()
    container_service.create_container.return_value = "container-123"
    state_store = _DummyStateStore()
    service = SessionService(container_service=container_service, state_store=state_store)

    before = datetime.now(timezone.utc)
    record = await service.create_session(
        server_id="server-a",
        image="ghcr.io/example/server:1.0.0",
        env={"TOKEN": "bw://item"},
        bw_session_key="bw-session",
        correlation_id="corr-1",
    )

    # docker create 呼び出しにリソース制限と分離設定が含まれる
    container_service.create_container.assert_awaited()
    config_arg = container_service.create_container.call_args[0][0]
    assert config_arg.cpus == 0.5
    assert config_arg.memory_limit == "512m"
    assert config_arg.network_mode == "none"
    assert config_arg.labels.get("mcp.session_id") == record.session_id
    assert config_arg.labels.get("mcp.server_id") == "server-a"

    # idle_deadline が約 30 分後に設定され、セッションはストアに保存される
    lower_bound = before + timedelta(minutes=29, seconds=50)
    upper_bound = before + timedelta(minutes=30, seconds=10)
    assert lower_bound <= record.idle_deadline <= upper_bound
    assert state_store.get_session(record.session_id) == record


@pytest.mark.asyncio
async def test_create_session_retries_once_on_failure() -> None:
    """コンテナ作成が 1 回失敗しても 2 回目で成功すればセッションが作成される。"""
    container_service = AsyncMock()
    container_service.create_container.side_effect = [
        ContainerError("first failure"),
        "container-ok",
    ]
    state_store = _DummyStateStore()
    service = SessionService(container_service=container_service, state_store=state_store)

    record = await service.create_session(
        server_id="server-b",
        image="ghcr.io/example/server:2.0.0",
        env={},
        bw_session_key="bw-session",
        correlation_id="corr-2",
    )

    assert container_service.create_container.await_count == 2
    assert record.gateway_endpoint.endswith("container-ok")
    assert state_store.get_session(record.session_id) is not None


@pytest.mark.asyncio
async def test_create_session_raises_after_two_failures() -> None:
    """コンテナ作成が連続で失敗した場合は例外を送出し、ストアへ保存しない。"""
    container_service = AsyncMock()
    container_service.create_container.side_effect = [
        ContainerError("first failure"),
        ContainerError("second failure"),
    ]
    state_store = _DummyStateStore()
    service = SessionService(container_service=container_service, state_store=state_store)

    with pytest.raises(ContainerError):
        await service.create_session(
            server_id="server-c",
            image="ghcr.io/example/server:3.0.0",
            env={},
            bw_session_key="bw-session",
            correlation_id="corr-3",
        )

    assert container_service.create_container.await_count == 2
    assert state_store.saved == []
