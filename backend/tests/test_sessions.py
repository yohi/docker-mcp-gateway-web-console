"""SessionService のセッション作成および実行管理を検証するテスト。"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import AsyncMock

import pytest

from app.models.state import JobRecord, SessionRecord
from app.models.signature import (
    PermitUnsignedEntry,
    SignaturePolicy,
    SignatureVerificationError,
)
from app.services.containers import ContainerError
from app.services.metrics import MetricsRecorder
from app.services.sessions import SessionService


class _DummyStateStore:
    """永続化ストアの代替実装（メモリ保持のみ）。"""

    def __init__(self) -> None:
        self.sessions: Dict[str, SessionRecord] = {}
        self.jobs: Dict[str, JobRecord] = {}
        self.audit_logs: List[Dict[str, object]] = []

    def save_session(self, record: SessionRecord) -> None:
        self.sessions[record.session_id] = record

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)

    def save_job(self, record: JobRecord) -> None:
        self.jobs[record.job_id] = record

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self.jobs.get(job_id)

    def record_audit_log(
        self, event_type: str, correlation_id: str, metadata: Dict[str, object], **_: object
    ) -> None:
        """監査ログをメモリに保持する（テスト用）。"""
        self.audit_logs.append(
            {
                "event_type": event_type,
                "correlation_id": correlation_id,
                "metadata": metadata,
            }
        )


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
async def test_create_session_cleans_mtls_bundle_on_failure(tmp_path: Path) -> None:
    """コンテナ起動に失敗した場合でも一時証明書ディレクトリを掃除する。"""
    container_service = AsyncMock()
    container_service.create_container.side_effect = ContainerError("boom")
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
    )

    with pytest.raises(ContainerError):
        await service.create_session(
            server_id="server-fail",
            image="ghcr.io/example/server:fail",
            env={},
            bw_session_key="bw-session",
            correlation_id="corr-fail",
        )

    assert state_store.sessions == {}
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_create_session_blocks_when_signature_verification_fails(
    tmp_path: Path,
) -> None:
    """署名検証が enforcement で失敗した場合はコンテナ起動を中断する。"""
    container_service = AsyncMock()
    signature_verifier = AsyncMock()
    signature_verifier.verify_image.side_effect = SignatureVerificationError(
        error_code="invalid_signature",
        message="署名が無効です",
        remediation="鍵の配布を確認してください",
    )
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
        signature_verifier=signature_verifier,
    )
    policy = SignaturePolicy(
        verify_signatures=True,
        mode="enforcement",
        permit_unsigned=[],
        allowed_algorithms=["RSA-PSS-SHA256"],
    )

    with pytest.raises(SignatureVerificationError):
        await service.create_session(
            server_id="server-signature",
            image="ghcr.io/example/server:9.9.9",
            env={},
            bw_session_key="bw-session",
            correlation_id="corr-sig-fail",
            signature_policy=policy,
        )

    signature_verifier.verify_image.assert_awaited_once()
    container_service.create_container.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_session_skips_when_permit_unsigned_matches(
    tmp_path: Path,
) -> None:
    """permit_unsigned にマッチする場合は署名検証をスキップする。"""
    container_service = AsyncMock()
    container_service.create_container.return_value = "container-permit"
    signature_verifier = AsyncMock()
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
        signature_verifier=signature_verifier,
    )
    image = "ghcr.io/example/server:1.2.3"
    policy = SignaturePolicy(
        verify_signatures=True,
        mode="enforcement",
        permit_unsigned=[PermitUnsignedEntry(type="image", name=image)],
        allowed_algorithms=["RSA-PSS-SHA256"],
    )

    record = await service.create_session(
        server_id="server-permit",
        image=image,
        env={},
        bw_session_key="bw-session",
        correlation_id="corr-sig-permit",
        signature_policy=policy,
    )

    signature_verifier.verify_image.assert_not_awaited()
    container_service.create_container.assert_awaited_once()
    assert state_store.get_session(record.session_id) is not None


@pytest.mark.asyncio
async def test_create_session_skips_when_permit_unsigned_none(tmp_path: Path) -> None:
    """permit_unsigned に none が含まれる場合は署名検証をスキップする。"""
    container_service = AsyncMock()
    container_service.create_container.return_value = "container-permit-none"
    signature_verifier = AsyncMock()
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
        signature_verifier=signature_verifier,
    )
    image = "ghcr.io/example/server:1.2.3"
    policy = SignaturePolicy(
        verify_signatures=True,
        mode="enforcement",
        permit_unsigned=[PermitUnsignedEntry(type="none")],
        allowed_algorithms=["RSA-PSS-SHA256"],
    )

    record = await service.create_session(
        server_id="server-permit-none",
        image=image,
        env={},
        bw_session_key="bw-session",
        correlation_id="corr-sig-permit-none",
        signature_policy=policy,
    )

    signature_verifier.verify_image.assert_not_awaited()
    container_service.create_container.assert_awaited_once()
    assert state_store.get_session(record.session_id) is not None


@pytest.mark.asyncio
async def test_create_session_skips_when_permit_unsigned_digest(tmp_path: Path) -> None:
    """ダイジェスト指定の permit_unsigned にマッチする場合は検証をスキップする。"""
    container_service = AsyncMock()
    container_service.create_container.return_value = "container-permit-digest"
    signature_verifier = AsyncMock()
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
        signature_verifier=signature_verifier,
    )
    digest = "sha256:" + "a" * 64
    image = f"ghcr.io/example/server@{digest}"
    policy = SignaturePolicy(
        verify_signatures=True,
        mode="enforcement",
        permit_unsigned=[PermitUnsignedEntry(type="sha256", digest=digest)],
        allowed_algorithms=["RSA-PSS-SHA256"],
    )

    record = await service.create_session(
        server_id="server-permit-digest",
        image=image,
        env={},
        bw_session_key="bw-session",
        correlation_id="corr-sig-permit-digest",
        signature_policy=policy,
    )

    signature_verifier.verify_image.assert_not_awaited()
    container_service.create_container.assert_awaited_once()
    assert state_store.get_session(record.session_id) is not None


@pytest.mark.asyncio
async def test_create_session_skips_when_permit_unsigned_thumbprint(
    tmp_path: Path,
) -> None:
    """サムプリント指定の permit_unsigned にマッチする場合は検証をスキップする。"""
    container_service = AsyncMock()
    container_service.create_container.return_value = "container-permit-thumb"
    signature_verifier = AsyncMock()
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
        signature_verifier=signature_verifier,
    )
    thumbprint = "ABCDEF1234567890"
    image = "ghcr.io/example/server:thumb"
    policy = SignaturePolicy(
        verify_signatures=True,
        mode="enforcement",
        permit_unsigned=[PermitUnsignedEntry(type="thumbprint", cert=thumbprint)],
        allowed_algorithms=["RSA-PSS-SHA256"],
    )

    record = await service.create_session(
        server_id="server-permit-thumb",
        image=image,
        env={},
        bw_session_key="bw-session",
        correlation_id="corr-sig-permit-thumb",
        signature_policy=policy,
        image_thumbprint=thumbprint,
    )

    signature_verifier.verify_image.assert_not_awaited()
    container_service.create_container.assert_awaited_once()
    assert state_store.get_session(record.session_id) is not None


@pytest.mark.asyncio
async def test_create_session_allows_audit_only_on_failure(tmp_path: Path) -> None:
    """audit-only モードでは署名検証失敗時でも起動を継続する。"""
    container_service = AsyncMock()
    container_service.create_container.return_value = "container-audit"
    signature_verifier = AsyncMock()
    signature_verifier.verify_image.side_effect = SignatureVerificationError(
        error_code="invalid_signature",
        message="署名が無効です",
    )
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
        signature_verifier=signature_verifier,
    )
    policy = SignaturePolicy(
        verify_signatures=True,
        mode="audit-only",
        permit_unsigned=[],
        allowed_algorithms=["RSA-PSS-SHA256"],
    )

    record = await service.create_session(
        server_id="server-audit",
        image="ghcr.io/example/server:4.5.6",
        env={},
        bw_session_key="bw-session",
        correlation_id="corr-sig-audit",
        signature_policy=policy,
    )

    signature_verifier.verify_image.assert_awaited_once()
    container_service.create_container.assert_awaited_once()
    assert state_store.get_session(record.session_id) is not None
    assert state_store.audit_logs
    last_log = state_store.audit_logs[-1]
    assert last_log["metadata"]["error_code"] == "invalid_signature"
    assert last_log["metadata"]["mode"] == "audit-only"


@pytest.mark.asyncio
async def test_signature_verification_records_metrics_and_audit(tmp_path: Path) -> None:
    """署名検証成功時にメトリクスと監査ログが記録される。"""
    container_service = AsyncMock()
    container_service.create_container.return_value = "container-metrics"
    signature_verifier = AsyncMock()
    metrics = MetricsRecorder()
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
        signature_verifier=signature_verifier,
        metrics=metrics,
    )
    policy = SignaturePolicy(
        verify_signatures=True,
        mode="enforcement",
        permit_unsigned=[],
        allowed_algorithms=["RSA-PSS-SHA256"],
    )

    record = await service.create_session(
        server_id="server-metrics",
        image="ghcr.io/example/server:5.6.7",
        env={},
        bw_session_key="bw-session",
        correlation_id="corr-sig-success",
        signature_policy=policy,
    )

    assert metrics.get_counter(
        "signature_verification_total",
        {"mode": "enforcement", "result": "success"},
    ) == 1
    assert any(
        log["event_type"] == "signature_verification_success"
        and log["correlation_id"] == "corr-sig-success"
        for log in state_store.audit_logs
    )
    assert record.mtls_cert_ref is not None


@pytest.mark.asyncio
async def test_cleanup_session_removes_mtls_bundle(tmp_path: Path) -> None:
    """セッション終了時に mTLS バンドルが削除される。"""
    container_service = AsyncMock()
    container_service.create_container.return_value = "container-cleanup"
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
    )

    record = await service.create_session(
        server_id="server-cleanup",
        image="ghcr.io/example/server:8.8.8",
        env={},
        bw_session_key="bw-session",
        correlation_id="corr-cleanup",
    )

    bundle_dir = Path(record.mtls_cert_ref["cert_path"]).parent
    assert bundle_dir.exists()

    service.cleanup_session(record.session_id)

    assert state_store.get_session(record.session_id) is None
    assert not bundle_dir.exists()


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
async def test_update_session_config_clamps_out_of_range(tmp_path: Path) -> None:
    """設定値が範囲外の場合に上限・下限へ丸められる。"""
    container_service = AsyncMock()
    container_service.create_container.return_value = "container-clamp"
    state_store = _DummyStateStore()
    service = SessionService(
        container_service=container_service,
        state_store=state_store,
        cert_base_dir=tmp_path,
    )
    record = await service.create_session(
        server_id="server-clamp",
        image="ghcr.io/example/server:4.0.0",
        env={},
        bw_session_key="bw-session",
        correlation_id="corr-clamp",
    )

    updated = await service.update_session_config(
        session_id=record.session_id,
        max_run_seconds=999,
        output_bytes_limit=5_000_000,
    )

    runtime = updated.config.get("runtime", {})
    assert runtime["max_run_seconds"] == 300
    assert runtime["output_bytes_limit"] == 1_000_000


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
