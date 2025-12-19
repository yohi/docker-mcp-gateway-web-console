"""外部/E2B ゲートウェイ接続とヘルスチェックのサービス実装。"""

from __future__ import annotations

import asyncio
import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict, Iterable, List, Optional
from urllib.parse import urlparse

import httpx

from ..models.gateways import (
    GatewayAllowOverride,
    GatewayHealthPayload,
    GatewayRegistrationRequest,
)
from ..models.state import GatewayAllowEntry
from ..services.metrics import MetricsRecorder
from .state_store import StateStore

logger = logging.getLogger(__name__)


class GatewayError(Exception):
    """ゲートウェイ関連の基底例外。"""


class AllowlistError(GatewayError):
    """許可リスト検証エラー。"""


class HealthcheckError(GatewayError):
    """ヘルスチェック失敗時の例外。"""


class GatewayHealthResult(GatewayHealthPayload):
    """サービス内部でも利用するヘルスチェック結果。"""

    pass


@dataclass
class GatewayRecord:
    """登録済みゲートウェイの内部表現。"""

    gateway_id: str
    url: str
    token: str
    type: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_health: Optional[GatewayHealthResult] = None


class GatewayService:
    """外部/E2B ゲートウェイの登録とヘルスチェックを管理する。"""

    def __init__(
        self,
        state_store: Optional[StateStore] = None,
        healthcheck_runner: Optional[Callable[[GatewayRecord], Awaitable[GatewayHealthResult]]] = None,
        sleep_func: Callable[[float], Awaitable[object]] = asyncio.sleep,
        healthcheck_timeout_seconds: float = 15.0,
        backoff_seconds: Optional[List[float]] = None,
        enable_periodic: bool = True,
        periodic_interval_seconds: float = 300.0,
        metrics: Optional[MetricsRecorder] = None,
    ) -> None:
        self.state_store = state_store or StateStore()
        # スキーマを初期化しておく（テストや初回起動でも安全に動作させる）
        try:
            self.state_store.init_schema()
        except Exception as exc:  # noqa: BLE001
            logger.warning("StateStore の初期化に失敗しました: %s", exc)
        self._gateways: Dict[str, GatewayRecord] = {}
        self._periodic_tasks: Dict[str, asyncio.Task] = {}
        self._healthcheck_runner = healthcheck_runner
        self._sleep = sleep_func
        self._timeout = healthcheck_timeout_seconds
        self._backoff_seconds = backoff_seconds or [1.0, 2.0, 4.0]
        self._enable_periodic = enable_periodic
        self._periodic_interval = periodic_interval_seconds
        self.metrics = metrics or MetricsRecorder()

    def set_healthcheck_runner(
        self, runner: Callable[[GatewayRecord], Awaitable[GatewayHealthResult]]
    ) -> None:
        """ヘルスチェック実行関数を差し替える（テスト用フック）。"""
        self._healthcheck_runner = runner

    async def register_gateway(
        self, request: GatewayRegistrationRequest, correlation_id: Optional[str] = None
    ) -> GatewayRecord:
        """
        外部ゲートウェイを登録し、直後にヘルスチェックを実行する。

        Raises:
            AllowlistError: 許可リストに一致しない場合
            GatewayError: ヘルスチェックや保存に失敗した場合
        """
        entries = self._merge_allowlist(request.allowlist_overrides)
        try:
            self._validate_url_against_allowlist(str(request.url), request.type, entries)
            self.metrics.increment(
                "gateway_allowlist_total",
                {"result": "pass"},
            )
            self._record_allowlist_audit(
                action="gateway_allowlist_pass",
                target=correlation_id,
                url=str(request.url),
                gateway_type=request.type,
            )
        except AllowlistError:
            self.metrics.increment(
                "gateway_allowlist_total",
                {"result": "reject"},
            )
            self._record_allowlist_audit(
                action="gateway_allowlist_reject",
                target=correlation_id,
                url=str(request.url),
                gateway_type=request.type,
            )
            raise

        record = GatewayRecord(
            gateway_id=str(uuid.uuid4()),
            url=str(request.url),
            token=request.token,
            type=request.type,
        )
        self._gateways[record.gateway_id] = record

        # 監査ログ（トークンは StateStore 側でマスクされる）
        self.state_store.record_audit_log(
            category="gateways",
            action="gateway_registered",
            actor="system",
            target=correlation_id or record.gateway_id,
            metadata={"gateway_id": record.gateway_id, "url": record.url, "type": record.type},
        )

        record.last_health = await self._run_healthcheck(record)
        if self._enable_periodic:
            self._schedule_periodic_healthcheck(record.gateway_id)
        return record

    async def healthcheck(self, gateway_id: str) -> GatewayRecord:
        """
        登録済みゲートウェイに対して手動ヘルスチェックを実施する。

        Raises:
            GatewayError: 未登録またはヘルスチェック失敗時
        """
        record = self._gateways.get(gateway_id)
        if record is None:
            raise GatewayError("対象ゲートウェイが見つかりません。")

        record.last_health = await self._run_healthcheck(record)
        return record

    def _merge_allowlist(
        self, overrides: Iterable[GatewayAllowOverride]
    ) -> List[GatewayAllowEntry]:
        """
        許可リストをグローバル（DB）と上書き指定でマージする。

        - グローバルを基本とし、同一 ID の上書きは version の大きい方を採用。
        - disabled の項目は除外。
        """
        merged: Dict[str, GatewayAllowEntry] = {}
        for entry in sorted(self.state_store.list_gateway_allow_entries(), key=lambda e: e.version):
            merged[entry.id] = entry

        for override in overrides or []:
            existing = merged.get(override.id)
            if existing is None or override.version > existing.version:
                merged[override.id] = GatewayAllowEntry(
                    id=override.id,
                    type=override.type,
                    value=override.value,
                    created_by="override",
                    created_at=datetime.now(timezone.utc),
                    enabled=override.enabled,
                    version=override.version,
                )

        return [entry for entry in merged.values() if entry.enabled]

    def _validate_url_against_allowlist(
        self, url: str, gateway_type: str, entries: List[GatewayAllowEntry]
    ) -> None:
        """URL のスキーマと許可リスト一致を検証する。"""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise AllowlistError("URL スキーマが不正です（http/https のみ許可）。")

        domain = parsed.hostname or ""
        path = parsed.path or "/"

        for entry in entries:
            if entry.type == "domain" and self._domain_matches(domain, entry.value):
                return
            if entry.type == "pattern" and self._pattern_matches(domain, path, entry.value):
                return
            if entry.type == "service" and gateway_type == entry.value:
                return

        raise AllowlistError("許可リスト未登録のゲートウェイ URL です。")

    def _record_allowlist_audit(
        self,
        *,
        action: str,
        target: Optional[str],
        url: str,
        gateway_type: str,
    ) -> None:
        """allowlist 判定結果を監査ログに記録する。"""
        try:
            self.state_store.record_audit_log(
                category="gateways",
                action=action,
                actor="system",
                target=target or "gateway-allowlist",
                metadata={"url": url, "type": gateway_type},
            )
        except Exception:  # noqa: BLE001
            logger.warning("許可リスト監査ログの記録に失敗しました", exc_info=True)

    @staticmethod
    def _domain_matches(domain: str, allow_value: str) -> bool:
        """ドメイン末尾一致で検証する。"""
        return domain == allow_value or domain.endswith(f".{allow_value}")

    @staticmethod
    def _pattern_matches(domain: str, path: str, pattern: str) -> bool:
        """簡易パターンマッチ。domain+path を対象に '*' ワイルドカードを扱う。"""
        import fnmatch

        target = f"{domain}{path}"
        return fnmatch.fnmatch(target, pattern)

    async def _run_healthcheck(self, record: GatewayRecord) -> GatewayHealthResult:
        """ヘルスチェックランナーを実行する。"""
        runner = self._healthcheck_runner or self._default_healthcheck_runner
        result = await runner(record)
        self._record_health_metrics(result)
        return result

    async def _default_healthcheck_runner(self, record: GatewayRecord) -> GatewayHealthResult:
        """/healthcheck に対して 1→2→4s バックオフで最大 3 回リトライする。"""
        delays = [0.0] + self._backoff_seconds
        latencies: List[float] = []
        last_error: Optional[str] = None

        for idx, delay in enumerate(delays):
            if delay > 0:
                await self._sleep(delay)

            try:
                latency = await self._check_once(record.url, record.token)
                latencies.append(latency)
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                logger.warning(
                    "ヘルスチェック失敗 (%s/%s) id=%s reason=%s",
                    idx + 1,
                    len(delays),
                    record.gateway_id,
                    last_error,
                )

        return self._build_health_result(latencies, last_error)

    async def shutdown(self) -> None:
        """すべての定期タスクをキャンセルしてクリーンアップする。"""
        tasks = list(self._periodic_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._periodic_tasks.clear()

    def _schedule_periodic_healthcheck(self, gateway_id: str) -> None:
        """5 分間隔の定期ヘルスチェックをスケジュールする。"""
        if gateway_id in self._periodic_tasks:
            return

        async def _runner() -> None:
            while True:
                try:
                    await self._sleep(self._periodic_interval)
                    record = self._gateways.get(gateway_id)
                    if record is None:
                        self._periodic_tasks.pop(gateway_id, None)
                        break
                    record.last_health = await self._run_healthcheck(record)
                except asyncio.CancelledError:
                    self._periodic_tasks.pop(gateway_id, None)
                    break
                except Exception as exc:  # noqa: BLE001
                    logger.warning("定期ヘルスチェックでエラー: %s", exc)

        task = asyncio.create_task(_runner())
        self._periodic_tasks[gateway_id] = task

    async def _check_once(self, base_url: str, token: str) -> float:
        """単回のヘルスチェックを実行しレイテンシ(ms)を返す。"""
        target = base_url.rstrip("/") + "/healthcheck"
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(target, headers=headers)
            response.raise_for_status()
        latency_ms = (time.perf_counter() - start) * 1000
        return latency_ms

    def _build_health_result(
        self, latencies: List[float], last_error: Optional[str]
    ) -> GatewayHealthResult:
        """レイテンシ配列から p50/p95/p99 を算出する。"""
        if not latencies:
            status = "unhealthy"
            return GatewayHealthResult(
                status=status, p50_ms=0.0, p95_ms=0.0, p99_ms=0.0, last_error=last_error
            )

        latencies_sorted = sorted(latencies)
        p50 = self._percentile(latencies_sorted, 50)
        p95 = self._percentile(latencies_sorted, 95)
        p99 = self._percentile(latencies_sorted, 99)
        status = "healthy" if last_error is None else "degraded"
        return GatewayHealthResult(
            status=status, p50_ms=p50, p95_ms=p95, p99_ms=p99, last_error=last_error
        )

    def _record_health_metrics(self, result: GatewayHealthResult) -> None:
        """ヘルスチェックのメトリクスを記録する。"""
        try:
            self.metrics.increment(
                "gateway_healthcheck_total",
                {"result": result.status},
            )
            labels = {"status": result.status}
            for value in (result.p50_ms, result.p95_ms, result.p99_ms):
                self.metrics.observe("gateway_healthcheck_latency_ms", value, labels)
            if result.last_error:
                self.metrics.increment(
                    "gateway_healthcheck_errors",
                    {"status": result.status, "category": "last_error"},
                )
        except Exception:  # noqa: BLE001
            logger.warning("ヘルスチェックメトリクスの記録に失敗しました", exc_info=True)

    @staticmethod
    def _percentile(values: List[float], percentile: int) -> float:
        """最小二乗線形補間でパーセンタイルを計算する。"""
        if not values:
            return 0.0
        if len(values) == 1:
            return float(values[0])

        k = (len(values) - 1) * (percentile / 100)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return float(values[int(k)])
        d0 = values[f] * (c - k)
        d1 = values[c] * (k - f)
        return float(d0 + d1)
