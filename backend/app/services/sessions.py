"""セッション生成・実行管理とゲートウェイコンテナ起動を扱うサービス。"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from app.config import settings
from app.models.containers import ContainerConfig
from app.models.signature import (
    PermitUnsignedEntry,
    SignaturePolicy,
    SignatureVerificationError,
)
from app.models.state import JobRecord, SessionRecord
from app.services.containers import ContainerError, ContainerService
from app.services.signature_verifier import NoopSignatureVerifier, SignatureVerifier
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
        signature_verifier: Optional[SignatureVerifier] = None,
    ) -> None:
        self.container_service = container_service
        self.state_store = state_store or StateStore()
        self.cert_base_dir = cert_base_dir or Path(settings.state_db_path).parent / "certs"
        self.cert_base_dir.mkdir(parents=True, exist_ok=True)
        self._job_tasks: Dict[str, asyncio.Task[None]] = {}
        self.signature_verifier = signature_verifier or NoopSignatureVerifier()

    async def create_session(
        self,
        server_id: str,
        image: str,
        env: Optional[Dict[str, str]],
        bw_session_key: str,
        correlation_id: str,
        *,
        idle_minutes: int = DEFAULT_IDLE_MINUTES,
        signature_policy: Optional[SignaturePolicy] = None,
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

        if signature_policy and signature_policy.verify_signatures:
            if not self._is_permitted_unsigned(image, signature_policy.permit_unsigned):
                try:
                    await self.signature_verifier.verify_image(
                        image=image,
                        policy=signature_policy,
                        correlation_id=correlation_id,
                    )
                except SignatureVerificationError as exc:
                    if signature_policy.mode == "audit-only":
                        self.state_store.record_audit_log(
                            event_type="signature_verification_failed",
                            correlation_id=correlation_id,
                            metadata={
                                "error_code": exc.error_code,
                                "message": exc.message,
                                "mode": signature_policy.mode,
                                "image": image,
                            },
                        )
                    else:
                        raise

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

        if record.status == "running" and job_id in self._job_tasks:
            task = self._job_tasks[job_id]
            if not task.done():
                await asyncio.wait({task}, timeout=0.05)
            if task.done():
                record = self.state_store.get_job(job_id) or record

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
                    config,
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

        try:
            result = await self._run_command(
                container_id=container_id,
                command=command,
                max_run_seconds=max_run_seconds,
                output_bytes_limit=output_bytes_limit,
            )
            job.status = "completed"
            job.output_ref = {
                "storage": "memory",
                "data": result.output,
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("Job %s failed: %s", job_id, exc)
            job.status = "failed"
            job.output_ref = {"storage": "memory", "data": str(exc)}
            result = ExecResult(
                output="",
                exit_code=-1,
                timeout=False,
                truncated=False,
                started_at=job.started_at or datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
        finally:
            self._job_tasks.pop(job_id, None)

        job.finished_at = result.finished_at
        job.exit_code = result.exit_code
        job.timeout = result.timeout
        job.truncated = result.truncated
        self.state_store.save_job(job)

    def _ensure_mtls_bundle(self, session_id: str) -> Dict[str, str]:
        """
        mTLS 用の証明書バンドルを生成する。

        - 既定（本番想定）では cryptography で CA/サーバー証明書と秘密鍵を生成し、
          600 パーミッションで保存する。
        - settings.mtls_placeholder_mode=True の場合のみ、ローカル開発・テスト向けに
          プレースホルダーファイルを出力する。
        """
        bundle_dir = self.cert_base_dir / session_id
        bundle_dir.mkdir(parents=True, exist_ok=True)
        cert_path = bundle_dir / "server.crt"
        key_path = bundle_dir / "server.key"
        ca_path = bundle_dir / "ca.crt"

        if settings.mtls_placeholder_mode:
            for path in (cert_path, key_path, ca_path):
                if not path.exists():
                    path.write_text(
                        f"generated-for-{session_id}-{path.name}\n", encoding="utf-8"
                    )
                os.chmod(path, 0o600)
            return {
                "bundle_dir": str(bundle_dir),
                "cert_path": str(cert_path),
                "key_path": str(key_path),
                "ca_path": str(ca_path),
            }

        not_before = datetime.now(timezone.utc) - timedelta(minutes=1)
        not_after = datetime.now(timezone.utc) + timedelta(days=365)

        try:
            ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            ca_subject = x509.Name(
                [
                    x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "mcp-gateway"),
                    x509.NameAttribute(NameOID.COMMON_NAME, "mcp-gateway-ca"),
                ]
            )
            ca_cert = (
                x509.CertificateBuilder()
                .subject_name(ca_subject)
                .issuer_name(ca_subject)
                .public_key(ca_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(not_before)
                .not_valid_after(not_after)
                .add_extension(
                    x509.BasicConstraints(ca=True, path_length=None), critical=True
                )
                .sign(ca_key, hashes.SHA256())
            )

            server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            server_subject = x509.Name(
                [
                    x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "mcp-gateway"),
                    x509.NameAttribute(
                        NameOID.COMMON_NAME, f"mcp-session-{session_id}"
                    ),
                ]
            )
            san = x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.DNSName(f"mcp-session-{session_id}"),
                    x509.DNSName(session_id),
                ]
            )
            server_cert = (
                x509.CertificateBuilder()
                .subject_name(server_subject)
                .issuer_name(ca_subject)
                .public_key(server_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(not_before)
                .not_valid_after(not_after)
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), False)
                .add_extension(
                    x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False
                )
                .add_extension(san, False)
                .sign(ca_key, hashes.SHA256())
            )

            key_bytes = server_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            cert_bytes = server_cert.public_bytes(serialization.Encoding.PEM)
            ca_bytes = ca_cert.public_bytes(serialization.Encoding.PEM)

            for path, data in (
                (key_path, key_bytes),
                (cert_path, cert_bytes),
                (ca_path, ca_bytes),
            ):
                path.write_bytes(data)
                os.chmod(path, 0o600)
        except Exception as exc:  # noqa: BLE001
            logger.exception("mTLS バンドル生成に失敗しました: %s", exc)
            for path in (cert_path, key_path, ca_path):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("mTLS バンドル生成失敗時の一時ファイル削除に失敗: %s", path)
            raise

        return {
            "bundle_dir": str(bundle_dir),
            "cert_path": str(cert_path),
            "key_path": str(key_path),
            "ca_path": str(ca_path),
        }

    def _is_permitted_unsigned(
        self, image: str, entries: List[PermitUnsignedEntry]
    ) -> bool:
        """未署名を許容する条件に合致するかを判定する。"""
        for entry in entries:
            if entry.type == "any":
                return True
            if entry.type == "image" and entry.name and entry.name == image:
                return True
            if entry.type == "sha256" and entry.digest and entry.digest == image:
                return True
            if entry.type == "thumbprint" and entry.cert and entry.cert == image:
                return True
        return False

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
