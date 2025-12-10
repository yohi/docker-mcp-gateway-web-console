"""SessionService のセッション作成および実行管理を検証するテスト。"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import AsyncMock

import pytest

from app.models.state import JobRecord, SessionRecord
from app.services.containers import ContainerError
from app.services.sessions import SessionService


class _DummyStateStore:
    """永続化ストアの代替実装（メモリ保持のみ）。"""

    def __init__(self) -> None:
        self.sessions: Dict[str, SessionRecord] = {}
        self.jobs: Dict[str, JobRecord] = {}

    def save_session(self, record: SessionRecord) -> None:
        self.sessions[record.session_id] = record

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        return self.sessions.get(session_id)

    def save_job(self, record: JobRecord) -> None:
        self.jobs[record.job_id] = record

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self.jobs.get(job_id)

    def record_audit_log(self, *args, **kwargs) -> None:  # pragma: no cover - テスト用スタブ
        return None


@pytest.mark.asyncio
async def test_create_session_applies_isolation_and_limits(tmp_path: Path) -> None:
    """
    セッション作成時にネットワーク分離と cgroup 制限が付与され、
    idle_deadline が 30 分先に設定されることを検証する。
    さらに mTLS バンドルが生成され、ボリュームマウントが付与される。
    """
    container_service = AsyncMock()
    container_service.create_container.return_value = "container-123"
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
    )

    before = datetime.now(timezone.utc)
    record = await service.create_session(
        server_id="server-a",
        image="ghcr.io/example/server:1.0.0",
        env={"TOKEN": "bw://item"},
        bw_session_key="bw-session",
        correlation_id="corr-1",
    )

    container_service.create_container.assert_awaited()
    config_arg = container_service.create_container.call_args[0][0]
    assert config_arg.cpus == 0.5
    assert config_arg.memory_limit == "512m"
    assert config_arg.network_mode == "none"
    assert config_arg.labels.get("mcp.session_id") == record.session_id
    assert config_arg.labels.get("mcp.server_id") == "server-a"
    assert config_arg.volumes  # mTLS バンドルをマウントしていること

    lower_bound = before + timedelta(minutes=29, seconds=50)
    upper_bound = before + timedelta(minutes=30, seconds=10)
    assert lower_bound <= record.idle_deadline <= upper_bound
    saved = state_store.get_session(record.session_id)
    assert saved == record
    assert record.mtls_cert_ref is not None
    cert_paths = [
        Path(record.mtls_cert_ref["cert_path"]),
        Path(record.mtls_cert_ref["key_path"]),
        Path(record.mtls_cert_ref["ca_path"]),
    ]
    for path in cert_paths:
        assert path.exists()


@pytest.mark.asyncio
async def test_create_session_retries_once_on_failure(tmp_path: Path) -> None:
    """コンテナ作成が 1 回失敗しても 2 回目で成功すればセッションが作成される。"""
    container_service = AsyncMock()
    container_service.create_container.side_effect = [
        ContainerError("first failure"),
        "container-ok",
    ]
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
    )

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
async def test_create_session_raises_after_two_failures(tmp_path: Path) -> None:
    """コンテナ作成が連続で失敗した場合は例外を送出し、ストアへ保存しない。"""
    container_service = AsyncMock()
    container_service.create_container.side_effect = [
        ContainerError("first failure"),
        ContainerError("second failure"),
    ]
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
    )

    with pytest.raises(ContainerError):
        await service.create_session(
            server_id="server-c",
            image="ghcr.io/example/server:3.0.0",
            env={},
            bw_session_key="bw-session",
            correlation_id="corr-3",
        )

    assert container_service.create_container.await_count == 2
    assert state_store.sessions == {}


@pytest.mark.asyncio
async def test_update_session_config_persists_runtime_limits(tmp_path: Path) -> None:
    """max_run_seconds と output_bytes_limit の更新が永続化される。"""
    container_service = AsyncMock()
    container_service.create_container.return_value = "container-123"
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
    )
    record = await service.create_session(
        server_id="server-d",
        image="ghcr.io/example/server:4.0.0",
        env={},
        bw_session_key="bw-session",
        correlation_id="corr-4",
    )

    updated = await service.update_session_config(
        session_id=record.session_id,
        max_run_seconds=120,
        output_bytes_limit=64000,
    )

    runtime = updated.config.get("runtime", {})
    assert runtime["max_run_seconds"] == 120
    assert runtime["output_bytes_limit"] == 64000
    saved = state_store.get_session(record.session_id)
    assert saved is not None
    assert saved.config.get("runtime", {}).get("max_run_seconds") == 120


@pytest.mark.asyncio
async def test_execute_sync_applies_timeout_and_truncation(tmp_path: Path) -> None:
    """同期実行でタイムアウト/トランケーションが適用される。"""
    container_service = AsyncMock()
    container_service.create_container.return_value = "container-789"
    container_service.exec_command.return_value = (0, b"A" * 130_000)
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
    )
    record = await service.create_session(
        server_id="server-e",
        image="ghcr.io/example/server:5.0.0",
        env={},
        bw_session_key="bw-session",
        correlation_id="corr-5",
    )

    result = await service.execute_command(
        session_id=record.session_id,
        tool="echo",
        args=["hello"],
        async_mode=False,
        max_run_seconds=1,
        output_bytes_limit=50_000,
    )

    container_service.exec_command.assert_awaited()
    assert result.exit_code == 0
    assert result.timeout is False
    assert result.truncated is True
    assert len(result.output.encode("utf-8")) == 50_000


@pytest.mark.asyncio
async def test_execute_timeout_sets_exit_code_124(tmp_path: Path) -> None:
    """実行がタイムアウトした場合に exit_code=124 として扱う。"""
    container_service = AsyncMock()
    container_service.create_container.return_value = "container-timeout"
    container_service.exec_command.side_effect = asyncio.TimeoutError
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
    )
    record = await service.create_session(
        server_id="server-f",
        image="ghcr.io/example/server:6.0.0",
        env={},
        bw_session_key="bw-session",
        correlation_id="corr-6",
    )

    result = await service.execute_command(
        session_id=record.session_id,
        tool="sleep",
        args=["2"],
        async_mode=False,
        max_run_seconds=1,
    )

    assert result.timeout is True
    assert result.exit_code == 124
    assert result.output == ""
    assert result.truncated is False


@pytest.mark.asyncio
async def test_execute_async_records_job_result(tmp_path: Path) -> None:
    """非同期実行でジョブ状態と出力が保存・取得できる。"""
    async def _exec_command(container_id: str, command: List[str]) -> tuple[int, bytes]:
        await asyncio.sleep(0)
        return 0, b"async-output"

    container_service = AsyncMock()
    container_service.create_container.return_value = "container-async"
    container_service.exec_command.side_effect = _exec_command
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
    )
    record = await service.create_session(
        server_id="server-g",
        image="ghcr.io/example/server:7.0.0",
        env={},
        bw_session_key="bw-session",
        correlation_id="corr-7",
    )

    job = await service.execute_command(
        session_id=record.session_id,
        tool="echo",
        args=["hello"],
        async_mode=True,
    )

    # バックグラウンドタスクの完了を待機
    await asyncio.sleep(0)

    status = await service.get_job_status(job.job_id)
    assert status is not None
    assert status.status == "completed"
    assert status.output == "async-output"
    assert status.exit_code == 0

    saved_job = state_store.get_job(job.job_id)
    assert saved_job is not None
    assert saved_job.status == "completed"
