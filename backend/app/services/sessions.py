"""セッション生成・実行管理とゲートウェイコンテナ起動を扱うサービス。"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from app.config import settings
from app.models.containers import ContainerConfig
from app.models.state import JobRecord, SessionRecord
from app.services.containers import ContainerError, ContainerService
from app.services.state_store import StateStore

logger = logging.getLogger(__name__)

# デフォルトのリソース制限・タイムアウト
DEFAULT_CPU_QUOTA = 0.5
DEFAULT_MEMORY_LIMIT = "512m"
DEFAULT_IDLE_MINUTES = 30
DEFAULT_MAX_RUN_SECONDS = 60
MIN_MAX_RUN_SECONDS = 10
MAX_MAX_RUN_SECONDS = 300
DEFAULT_OUTPUT_BYTES_LIMIT = 128_000
MIN_OUTPUT_BYTES_LIMIT = 32_000
MAX_OUTPUT_BYTES_LIMIT = 1_000_000
MTLS_MOUNT_PATH = "/etc/mcp-certs"


@dataclass
class ExecResult:
    """コマンド実行結果の表現。"""

    output: str
    exit_code: int
    timeout: bool
    truncated: bool
    started_at: datetime
    finished_at: datetime


@dataclass
class JobStatus:
    """ジョブ状態の表現。"""

    job_id: str
    status: str
    output: Optional[str]
    exit_code: Optional[int]
    timeout: bool
    truncated: bool
    started_at: Optional[datetime]
    finished_at: Optional[datetime]


class SessionService:
    """セッション単位でゲートウェイコンテナを起動・保存し、実行を管理する。"""

    def __init__(
        self,
        container_service: ContainerService,
        state_store: Optional[StateStore] = None,
        cert_base_dir: Optional[Path] = None,
    ) -> None:
        self.container_service = container_service
        self.state_store = state_store or StateStore()
        self.cert_base_dir = cert_base_dir or Path(settings.state_db_path).parent / "certs"
        self.cert_base_dir.mkdir(parents=True, exist_ok=True)
        self._job_tasks: Dict[str, asyncio.Task[None]] = {}

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
        - mTLS 用の自己署名バンドルを生成し、ボリュームとしてマウントする
        """
        session_id = uuid4().hex
        labels = {
            "mcp.session_id": session_id,
            "mcp.server_id": server_id,
        }

        mtls_bundle = self._ensure_mtls_bundle(session_id)
        config = ContainerConfig(
            name=f"mcp-session-{session_id[:8]}",
            image=image,
            env=env or {},
            network_mode="none",
            labels=labels,
            cpus=DEFAULT_CPU_QUOTA,
            memory_limit=DEFAULT_MEMORY_LIMIT,
            restart_policy={"Name": "on-failure", "MaximumRetryCount": 1},
            volumes={mtls_bundle["bundle_dir"]: MTLS_MOUNT_PATH},
        )

        container_id = await self._create_with_retry(
            config=config,
            session_id=session_id,
            bw_session_key=bw_session_key,
            correlation_id=correlation_id,
        )

        idle_deadline = datetime.now(timezone.utc) + timedelta(minutes=idle_minutes)
        runtime_cfg = {
            "max_run_seconds": DEFAULT_MAX_RUN_SECONDS,
            "output_bytes_limit": DEFAULT_OUTPUT_BYTES_LIMIT,
        }
        merged_config = config.model_dump()
        merged_config["runtime"] = runtime_cfg

        record = SessionRecord(
            session_id=session_id,
            server_id=server_id,
            config=merged_config,
            state="running",
            idle_deadline=idle_deadline,
            gateway_endpoint=f"container://{container_id}",
            metrics_endpoint="",
            mtls_cert_ref={
                "type": "file",
                "cert_path": mtls_bundle["cert_path"],
                "key_path": mtls_bundle["key_path"],
                "ca_path": mtls_bundle["ca_path"],
            },
            feature_flags={"cost_priority": False},
        )
        self.state_store.save_session(record)
        return record

    async def update_session_config(
        self,
        session_id: str,
        *,
        max_run_seconds: Optional[int] = None,
        output_bytes_limit: Optional[int] = None,
    ) -> SessionRecord:
        """セッションの実行設定を保存・反映する。"""
        record = self.state_store.get_session(session_id)
        if record is None:
            raise ValueError("Session not found")

        runtime = record.config.get("runtime", {})
        runtime["max_run_seconds"] = self._clamp_max_run_seconds(
            max_run_seconds or runtime.get("max_run_seconds", DEFAULT_MAX_RUN_SECONDS)
        )
        runtime["output_bytes_limit"] = self._clamp_output_bytes_limit(
            output_bytes_limit
            or runtime.get("output_bytes_limit", DEFAULT_OUTPUT_BYTES_LIMIT)
        )
        record.config["runtime"] = runtime
        self.state_store.save_session(record)
        return record

    async def execute_command(
        self,
        session_id: str,
        tool: str,
        args: Optional[List[str]] = None,
        *,
        async_mode: bool = False,
        max_run_seconds: Optional[int] = None,
        output_bytes_limit: Optional[int] = None,
    ) -> ExecResult | JobRecord:
        """
        mcp-exec 相当のコマンドを同期/非同期で実行する。

        - max_run_seconds でタイムアウトし、TimeoutError 時は exit_code=124 とする
        - output_bytes_limit を超える場合は末尾を切り詰めて truncated=True にする
        - 非同期モードでは JobRecord を返し、バックグラウンドで実行する
        """
        record = self.state_store.get_session(session_id)
        if record is None:
            raise ValueError("Session not found")

        runtime = record.config.get("runtime", {})
        max_run_seconds = self._clamp_max_run_seconds(
            max_run_seconds or runtime.get("max_run_seconds", DEFAULT_MAX_RUN_SECONDS)
        )
        output_bytes_limit = self._clamp_output_bytes_limit(
            output_bytes_limit
            or runtime.get("output_bytes_limit", DEFAULT_OUTPUT_BYTES_LIMIT)
        )

        container_id = self._extract_container_id(record.gateway_endpoint)
        command = self._build_command(tool, args or [])

        if async_mode:
            job_id = uuid4().hex
            queued_at = datetime.now(timezone.utc)
            job = JobRecord(
                job_id=job_id,
                session_id=session_id,
                status="queued",
                queued_at=queued_at,
                started_at=None,
                finished_at=None,
                exit_code=None,
                timeout=False,
                truncated=False,
                output_ref=None,
            )
            self.state_store.save_job(job)
            task = asyncio.create_task(
                self._execute_job(
                    job_id=job_id,
                    session_id=session_id,
                    container_id=container_id,
                    command=command,
                    max_run_seconds=max_run_seconds,
                    output_bytes_limit=output_bytes_limit,
                )
            )
            self._job_tasks[job_id] = task
            return job

        return await self._run_command(
            container_id=container_id,
            command=command,
            max_run_seconds=max_run_seconds,
            output_bytes_limit=output_bytes_limit,
        )

    async def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """ジョブの現在の状態を返す。"""
        record = self.state_store.get_job(job_id)
        if record is None:
            return None

        output: Optional[str] = None
        if record.output_ref and record.output_ref.get("storage") == "memory":
            output = record.output_ref.get("data")  # type: ignore[arg-type]

        return JobStatus(
            job_id=record.job_id,
            status=record.status,
            output=output,
            exit_code=record.exit_code,
            timeout=record.timeout,
            truncated=record.truncated,
            started_at=record.started_at,
            finished_at=record.finished_at,
        )

    async def _execute_with_retry(
        self,
        *,
        func_name: str,
        attempt: int,
        correlation_id: str,
        exc: Exception,
    ) -> None:
        logger.warning(
            "Session container creation failed (attempt=%s, correlation_id=%s): %s",
            attempt,
            correlation_id,
            exc,
        )

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
                await self._execute_with_retry(
                    func_name="create_container",
                    attempt=attempt + 1,
                    correlation_id=correlation_id,
                    exc=exc,
                )
                if attempt == 0:
                    continue
                raise

        if last_error:
            raise last_error
        raise ContainerError("Unknown error while creating session container")

    async def _run_command(
        self,
        *,
        container_id: str,
        command: List[str],
        max_run_seconds: int,
        output_bytes_limit: int,
    ) -> ExecResult:
        """コンテナ上でコマンドを実行し、タイムアウトとトランケーションを適用する。"""
        started_at = datetime.now(timezone.utc)
        timeout = False
        try:
            exit_code, output_bytes = await asyncio.wait_for(
                self.container_service.exec_command(container_id, command),
                timeout=max_run_seconds,
            )
        except asyncio.TimeoutError:
            exit_code = 124
            output_bytes = b""
            timeout = True
        finished_at = datetime.now(timezone.utc)

        output_text = output_bytes.decode("utf-8", errors="replace")
        encoded = output_text.encode("utf-8")
        truncated = False
        if len(encoded) > output_bytes_limit:
            truncated = True
            encoded = encoded[:output_bytes_limit]
            output_text = encoded.decode("utf-8", errors="replace")

        return ExecResult(
            output=output_text,
            exit_code=exit_code,
            timeout=timeout,
            truncated=truncated,
            started_at=started_at,
            finished_at=finished_at,
        )

    async def _execute_job(
        self,
        *,
        job_id: str,
        session_id: str,
        container_id: str,
        command: List[str],
        max_run_seconds: int,
        output_bytes_limit: int,
    ) -> None:
        """バックグラウンドでジョブを実行し、状態を保存する。"""
        job = self.state_store.get_job(job_id)
        if job is None:
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        self.state_store.save_job(job)

        result = await self._run_command(
            container_id=container_id,
            command=command,
            max_run_seconds=max_run_seconds,
            output_bytes_limit=output_bytes_limit,
        )

        job.status = "completed"
        job.finished_at = result.finished_at
        job.exit_code = result.exit_code
        job.timeout = result.timeout
        job.truncated = result.truncated
        job.output_ref = {
            "storage": "memory",
            "data": result.output,
        }
        self.state_store.save_job(job)
        self._job_tasks.pop(job_id, None)

    def _ensure_mtls_bundle(self, session_id: str) -> Dict[str, str]:
        """自己署名証明書のプレースホルダーを生成し、パス情報を返す。"""
        bundle_dir = self.cert_base_dir / session_id
        bundle_dir.mkdir(parents=True, exist_ok=True)
        cert_path = bundle_dir / "server.crt"
        key_path = bundle_dir / "server.key"
        ca_path = bundle_dir / "ca.crt"

        for path in (cert_path, key_path, ca_path):
            if not path.exists():
                path.write_text(f"generated-for-{session_id}-{path.name}\n", encoding="utf-8")

        return {
            "bundle_dir": str(bundle_dir),
            "cert_path": str(cert_path),
            "key_path": str(key_path),
            "ca_path": str(ca_path),
        }

    def _extract_container_id(self, gateway_endpoint: str) -> str:
        """gateway_endpoint からコンテナ ID を抽出する。"""
        if gateway_endpoint.startswith("container://"):
            return gateway_endpoint.split("container://", 1)[1]
        return gateway_endpoint

    def _build_command(self, tool: str, args: List[str]) -> List[str]:
        """mcp-exec を意識したコマンド配列を生成する。"""
        return ["mcp-exec", tool, *args]

    def _clamp_max_run_seconds(self, value: int) -> int:
        """max_run_seconds の許容範囲を強制する。"""
        return max(MIN_MAX_RUN_SECONDS, min(MAX_MAX_RUN_SECONDS, value))

    def _clamp_output_bytes_limit(self, value: int) -> int:
        """output_bytes_limit の許容範囲を強制する。"""
        return max(MIN_OUTPUT_BYTES_LIMIT, min(MAX_OUTPUT_BYTES_LIMIT, value))
