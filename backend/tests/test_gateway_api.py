"""外部ゲートウェイ API のTDDテスト。"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from app.api import gateways as gateways_api
from app.main import app
from app.models.gateways import GatewayRegistrationRequest
from app.models.state import GatewayAllowEntry
from app.services.gateways import GatewayHealthResult, GatewayService
from app.services.state_store import StateStore

client = TestClient(app)


@pytest.fixture
def state_store(tmp_path) -> StateStore:
    """テスト用の一時 SQLite ストアを準備する。"""
    db_path = tmp_path / "state.db"
    store = StateStore(str(db_path))
    store.init_schema()
    return store


@pytest.fixture
def allowlist_entry() -> Dict[str, Any]:
    """許可済みドメインのエントリ定義。"""
    return {
        "id": "allow-1",
        "type": "domain",
        "value": "example.com",
        "created_by": "admin",
        "created_at": datetime.now(timezone.utc),
        "enabled": True,
        "version": 1,
    }


@pytest.fixture
def stub_health_runner():
    """成功するヘルスチェックをスタブする。"""

    async def _runner(record):
        return GatewayHealthResult(
            status="healthy",
            p50_ms=12.0,
            p95_ms=15.0,
            p99_ms=20.0,
            last_error=None,
        )

    return _runner


@pytest.fixture
def gateway_service(state_store, allowlist_entry, stub_health_runner, monkeypatch):
    """API モジュールのゲートウェイサービスをテスト用に差し替える。"""
    state_store.save_gateway_allow_entry(GatewayAllowEntry(**allowlist_entry))
    service = GatewayService(
        state_store=state_store,
        healthcheck_runner=stub_health_runner,
        sleep_func=lambda *_: asyncio.sleep(0),
        enable_periodic=False,
    )
    monkeypatch.setattr(gateways_api, "gateway_service", service)
    return service


class TestGatewayAPI:
    """ゲートウェイ登録とヘルスチェックの振る舞いを検証する。"""

    def test_register_rejects_not_in_allowlist(self, gateway_service):
        """許可リストに無い URL は 400 を返す。"""
        payload = {
            "url": "https://unauthorized.test/service",
            "token": "secret-token",
            "type": "external",
        }

        response = client.post("/api/gateways?correlation_id=corr-allow-deny", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert "許可リスト未登録" in data["detail"]
        logs = gateway_service.state_store.get_recent_audit_logs(limit=5)
        assert any(
            log.event_type == "gateway_allowlist_reject" and log.correlation_id == "corr-allow-deny"
            for log in logs
        )
        assert gateway_service.metrics.get_counter(
            "gateway_allowlist_total", {"result": "reject"}
        ) == 1

    def test_register_runs_healthcheck_and_enables_external_mode(self, gateway_service):
        """登録成功時にヘルスチェック結果が返り外部モードが有効化される。"""
        payload = {
            "url": "https://example.com/service",
            "token": "secret-token",
            "type": "external",
        }

        response = client.post("/api/gateways?correlation_id=corr-allow-pass", json=payload)

        assert response.status_code == 200
        body = response.json()

        assert body["status"] == "healthy"
        assert body["health"]["p50_ms"] == 12.0
        assert body["health"]["p95_ms"] == 15.0
        assert body["health"]["p99_ms"] == 20.0
        assert body["external_mode_enabled"] is True
        # トークンがレスポンスに含まれないことを確認
        assert "token" not in body
        logs = gateway_service.state_store.get_recent_audit_logs(limit=5)
        assert any(
            log.event_type == "gateway_allowlist_pass" and log.correlation_id == "corr-allow-pass"
            for log in logs
        )
        assert gateway_service.metrics.get_counter(
            "gateway_allowlist_total", {"result": "pass"}
        ) == 1
        assert gateway_service.metrics.get_counter(
            "gateway_healthcheck_total", {"result": "healthy"}
        ) == 1
        observations = gateway_service.metrics.get_observations(
            "gateway_healthcheck_latency_ms", {"status": "healthy"}
        )
        assert observations  # いずれかのレイテンシが記録されていること

    def test_manual_health_endpoint_reuses_saved_gateway(self, gateway_service):
        """登録済みゲートウェイに対する手動ヘルスチェックを実行する。"""
        payload = {
            "url": "https://example.com/service",
            "token": "secret-token",
            "type": "external",
        }

        register_response = client.post("/api/gateways", json=payload)
        gateway_id = register_response.json()["gateway_id"]

        calls = {"count": 0}

        async def updated_runner(record):
            calls["count"] += 1
            return GatewayHealthResult(
                status="healthy",
                p50_ms=5.0,
                p95_ms=6.0,
                p99_ms=7.0,
                last_error=None,
            )

        gateway_service.set_healthcheck_runner(updated_runner)

        health_response = client.get(f"/api/gateways/{gateway_id}/health")

        assert health_response.status_code == 200
        body = health_response.json()
        assert body["health"]["p50_ms"] == 5.0
        assert body["health"]["p99_ms"] == 7.0
        assert calls["count"] == 1


@pytest.mark.asyncio
async def test_default_healthcheck_retries_with_backoff(
    monkeypatch, state_store, allowlist_entry
):
    """デフォルトのヘルスチェックが 1→2→4s バックオフで再試行することを検証する。"""
    state_store.save_gateway_allow_entry(GatewayAllowEntry(**allowlist_entry))

    delays = []

    async def fake_sleep(seconds: float):
        delays.append(seconds)

    attempts = {"count": 0}

    async def flaky_check(url: str, token: str) -> float:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary failure")
        return 12.5

    service = GatewayService(
        state_store=state_store,
        healthcheck_runner=None,  # デフォルトランナーを使う
        sleep_func=fake_sleep,
        backoff_seconds=[1.0, 2.0],
        enable_periodic=False,
    )
    monkeypatch.setattr(service, "_check_once", flaky_check)

    request = GatewayRegistrationRequest(
        url="https://example.com/service",
        token="secret-token",
        type="external",
        allowlist_overrides=[],
    )

    record = await service.register_gateway(request, correlation_id="corr-health-retry")

    assert attempts["count"] == 3
    assert delays == [1.0, 2.0]
    assert record.last_health is not None
    assert record.last_health.status == "healthy"
    assert (
        service.metrics.get_counter(
            "gateway_healthcheck_total", {"result": "healthy"}
        )
        == 1
    )
