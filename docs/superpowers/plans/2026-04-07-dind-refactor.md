# DinD リファクタリング実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** DooD (Docker-out-of-Docker) から DinD (Docker-in-Docker) + TLS Remote API へ移行し、同時に ContainerService に AuthService を DI して API ルーターを Thin Controller 化する。

**Architecture:** インフラ移行（Task 1-4）を先行させ、既存テストが TCP 経由で Green になることを確認してから、Service 層の TDD リファクタリング（Task 5-6）に着手する。API スキーマ・フロントエンドは無変更。

**Tech Stack:** Docker DinD, TLS (docker.tls.TLSConfig), FastAPI DI, Pytest, Python 3.14+

---

## ファイル構成

| 操作 | パス | 責務 |
|------|------|------|
| Modify | `.devcontainer/docker-compose.devcontainer.yml` | DinD サービス追加、ソケットマウント廃止 |
| Modify | `.devcontainer/devcontainer.json` | remoteEnv に DOCKER_HOST/TLS 設定追加 |
| Modify | `backend/app/config.py` | DOCKER_CERT_PATH 設定追加 |
| Modify | `backend/app/api/containers.py` | TLS 自動構成、Thin Controller 化 |
| Modify | `backend/app/services/containers.py` | AuthService DI、認証付きメソッド追加 |
| Create | `backend/tests/test_container_service_auth.py` | Service 層 Auth 連携テスト |
| Modify | `backend/tests/test_devcontainer_docker_socket.py` | DinD 構成テスト追加 |
| Modify | `backend/tests/test_devcontainer_config.py` | remoteEnv テスト追加 |
| Modify | `backend/tests/conftest.py` | TLS モック対応 |

---

### Task 1: ベースラインテスト確認

**Files:**
- Read: `backend/tests/`

- [ ] **Step 1: 既存テストを実行**

Run: `cd backend && python -m pytest tests/ -x -q --tb=short 2>&1 | tail -20`
Expected: All tests PASS (green baseline)

- [ ] **Step 2: 結果を記録**

テスト数と結果をメモする。失敗がある場合はこのプランの前に修正が必要。

---

### Task 2: docker-compose.devcontainer.yml の DinD 移行

**Files:**
- Modify: `.devcontainer/docker-compose.devcontainer.yml`
- Test: `backend/tests/test_devcontainer_docker_socket.py`

- [ ] **Step 1: テスト追加 — DinD 構成の検証 [Red]**

`backend/tests/test_devcontainer_docker_socket.py` の末尾に追加:

```python
def test_devcontainer_compose_dind_service() -> None:
    """DinD サービスが docker-compose.devcontainer.yml に定義されていること。"""
    import yaml
    repo_root = Path(__file__).resolve().parents[2]
    compose_path = repo_root / ".devcontainer" / "docker-compose.devcontainer.yml"
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = data.get("services", {})

    assert "dind" in services, "dind service must be defined"
    dind = services["dind"]
    assert "docker:dind" in str(dind.get("image", "")), "dind must use docker:dind image"
    assert dind.get("privileged") is True, "dind must be privileged"
    assert "healthcheck" in dind, "dind must have healthcheck"

    ws = services.get("workspace", {})
    ws_volumes = ws.get("volumes", [])
    for v in ws_volumes:
        assert "docker.sock" not in str(v), "workspace must not mount docker.sock"

    ws_depends = ws.get("depends_on", {})
    if isinstance(ws_depends, list):
        assert "dind" in ws_depends
    else:
        assert "dind" in ws_depends
```

- [ ] **Step 2: テスト実行 — 失敗確認**

Run: `cd backend && python -m pytest tests/test_devcontainer_docker_socket.py::test_devcontainer_compose_dind_service -xvs 2>&1 | tail -20`
Expected: FAIL (dind service not found)

- [ ] **Step 3: docker-compose.devcontainer.yml を更新**

`.devcontainer/docker-compose.devcontainer.yml` を以下に置き換え:

```yaml
services:
  dind:
    image: docker:dind
    privileged: true
    environment:
      - DOCKER_TLS_CERTDIR=/certs
    volumes:
      - dind-certs-ca:/certs/ca
      - dind-certs-client:/certs/client
      - dind-data:/var/lib/docker
    ports:
      - "8080-8090:8080-8090"
    healthcheck:
      test: ["CMD", "docker", "info"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s
    networks:
      - mcp-gateway

  workspace:
    build:
      context: .
      dockerfile: .devcontainer/Dockerfile.workspace
    volumes:
      - ..:/workspace:cached
      - dind-certs-client:/certs/client:ro
    environment:
      - DOCKER_HOST=tcp://dind:2376
      - DOCKER_TLS_VERIFY=1
      - DOCKER_CERT_PATH=/certs/client
    command: sleep infinity
    depends_on:
      dind:
        condition: service_healthy
      backend:
        condition: service_started
      frontend:
        condition: service_started

  backend:
    volumes:
      - ../backend:/app:cached
      - dind-certs-client:/certs/client:ro
    environment:
      - DOCKER_HOST=tcp://dind:2376
      - DOCKER_TLS_VERIFY=1
      - DOCKER_CERT_PATH=/certs/client
    depends_on:
      dind:
        condition: service_healthy

  frontend:
    volumes:
      - ../frontend:/app:cached
    shm_size: 1gb

volumes:
  dind-certs-ca:
  dind-certs-client:
  dind-data:
```

- [ ] **Step 4: 既存テスト test_devcontainer_compose_references_detected_socket を更新**

DinD 移行後はソケットマウント検証が不要。テストを DinD 構成の検証に変更:

```python
def test_devcontainer_compose_references_detected_socket() -> None:
    """DinD 移行後: workspace が DOCKER_HOST=tcp://dind:2376 を使用すること。"""
    repo_root = Path(__file__).resolve().parents[2]
    compose_path = repo_root / ".devcontainer" / "docker-compose.devcontainer.yml"

    assert compose_path.exists()
    content = compose_path.read_text(encoding="utf-8")

    assert "workspace:" in content
    assert "dind:" in content
    assert "tcp://dind:2376" in content
    assert "${DOCKER_SOCKET}:/var/run/docker.sock" not in content
```

- [ ] **Step 5: テスト実行 — 成功確認**

Run: `cd backend && python -m pytest tests/test_devcontainer_docker_socket.py -xvs 2>&1 | tail -20`
Expected: PASS

- [ ] **Step 6: PyYAML 依存の追加**

Run: `cd backend && grep -q pyyaml requirements-dev.txt || echo "pyyaml" >> requirements-dev.txt`

- [ ] **Step 7: コミット**

```bash
git add .devcontainer/docker-compose.devcontainer.yml backend/tests/test_devcontainer_docker_socket.py backend/requirements-dev.txt
git commit -m "feat(infra): DooD から DinD + TLS Remote API へ移行"
```

---

### Task 3: devcontainer.json と config.py の更新

**Files:**
- Modify: `.devcontainer/devcontainer.json`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_devcontainer_config.py`

- [ ] **Step 1: テスト追加 — remoteEnv 検証 [Red]**

`backend/tests/test_devcontainer_config.py` に追加:

```python
def test_devcontainer_json_has_docker_remote_env() -> None:
    """remoteEnv に DOCKER_HOST/TLS 設定が含まれること。"""
    devcontainer_json = _repo_root() / ".devcontainer" / "devcontainer.json"
    data = json.loads(devcontainer_json.read_text(encoding="utf-8"))

    remote_env = data.get("remoteEnv", {})
    assert "DOCKER_HOST" in remote_env
    assert "DOCKER_TLS_VERIFY" in remote_env
    assert "DOCKER_CERT_PATH" in remote_env
```

- [ ] **Step 2: テスト実行 — 失敗確認**

Run: `cd backend && python -m pytest tests/test_devcontainer_config.py::test_devcontainer_json_has_docker_remote_env -xvs`
Expected: FAIL

- [ ] **Step 3: devcontainer.json に remoteEnv を追加**

既存の JSON に `"remoteEnv"` セクションを追加:

```json
  "remoteEnv": {
    "DOCKER_HOST": "tcp://dind:2376",
    "DOCKER_TLS_VERIFY": "1",
    "DOCKER_CERT_PATH": "/certs/client"
  },
```

`"customizations"` の直前に挿入。

- [ ] **Step 4: config.py に DOCKER_CERT_PATH 設定を追加**

`backend/app/config.py` の `container_provider_type` の後に追加:

```python
    docker_cert_path: Optional[str] = Field(default=None, validation_alias="DOCKER_CERT_PATH")
```

- [ ] **Step 5: テスト実行 — 成功確認**

Run: `cd backend && python -m pytest tests/test_devcontainer_config.py -xvs 2>&1 | tail -10`
Expected: PASS

- [ ] **Step 6: コミット**

```bash
git add .devcontainer/devcontainer.json backend/app/config.py backend/tests/test_devcontainer_config.py
git commit -m "feat(infra): devcontainer.json に DOCKER_HOST/TLS remoteEnv を追加"
```

---

### Task 4: DockerSdkProvider の TLS 自動構成と conftest 更新

**Files:**
- Modify: `backend/app/api/containers.py` (get_container_provider)
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: get_container_provider を DOCKER_CERT_PATH ベースに更新**

`backend/app/api/containers.py` の `get_container_provider` を修正:

```python
def get_container_provider() -> ContainerProvider:
    """Dependency to get the container provider instance."""
    global _container_provider
    if _container_provider is None:
        tls_config = None
        cert_path = settings.docker_cert_path or os.environ.get("DOCKER_CERT_PATH")
        if settings.docker_tls_verify and cert_path:
            tls_config = docker.tls.TLSConfig(
                client_cert=(
                    os.path.join(cert_path, "cert.pem"),
                    os.path.join(cert_path, "key.pem"),
                ),
                ca_cert=os.path.join(cert_path, "ca.pem"),
                verify=True,
            )
        _container_provider = DockerSdkProvider(
            base_url=settings.docker_host,
            tls_config=tls_config,
        )
    return _container_provider
```

import セクションに `import os` を追加（先頭の `from ..config import settings` も追加）。

- [ ] **Step 2: conftest.py の TLS 環境変数クリア追加**

`backend/tests/conftest.py` の `_mock_docker_socket` フィクスチャ内、`os.environ["DOCKER_HOST"] = fake_host` の後に追加:

```python
    previous_tls_verify = os.environ.pop("DOCKER_TLS_VERIFY", None)
    previous_cert_path = os.environ.pop("DOCKER_CERT_PATH", None)
    previous_tls_setting = app_config.settings.docker_tls_verify
    app_config.settings.docker_tls_verify = False
```

finally ブロックの環境変数復元コードに追加:

```python
        if previous_tls_verify is not None:
            os.environ["DOCKER_TLS_VERIFY"] = previous_tls_verify
        if previous_cert_path is not None:
            os.environ["DOCKER_CERT_PATH"] = previous_cert_path
        app_config.settings.docker_tls_verify = previous_tls_setting
```

- [ ] **Step 3: 全テスト実行 — Green 確認**

Run: `cd backend && python -m pytest tests/ -x -q --tb=short 2>&1 | tail -20`
Expected: All tests PASS

- [ ] **Step 4: コミット**

```bash
git add backend/app/api/containers.py backend/tests/conftest.py
git commit -m "feat(infra): DockerSdkProvider の TLS 自動構成と DOCKER_CERT_PATH 対応"
```

---

### Task 5: Service 層の AuthService DI [Red → Green]

**Files:**
- Modify: `backend/app/services/containers.py`
- Create: `backend/tests/test_container_service_auth.py`

- [ ] **Step 1: テスト作成 [Red]**

`backend/tests/test_container_service_auth.py` を作成:

```python
"""ContainerService の AuthService DI テスト。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from app.models.auth import Session
from app.services.auth import AuthService
from app.services.containers import ContainerService


@pytest.fixture
def mock_provider() -> MagicMock:
    provider = MagicMock()
    provider.list_containers = AsyncMock(return_value=[])
    return provider


@pytest.fixture
def mock_secret_manager() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_auth_service() -> MagicMock:
    svc = MagicMock(spec=AuthService)
    svc.validate_session = AsyncMock(return_value=True)
    svc.get_session = AsyncMock(
        return_value=Session(
            session_id="test-sid",
            user_email="test@example.com",
            bw_session_key="test-bw-key",
            created_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-01T01:00:00Z",
            last_activity="2026-01-01T00:00:00Z",
        )
    )
    return svc


class TestContainerServiceWithAuth:
    def test_constructor_accepts_auth_service(
        self, mock_provider, mock_secret_manager, mock_auth_service
    ):
        svc = ContainerService(
            provider=mock_provider,
            secret_manager=mock_secret_manager,
            auth_service=mock_auth_service,
        )
        assert svc.auth_service is mock_auth_service

    @pytest.mark.asyncio
    async def test_validate_session_and_get(
        self, mock_provider, mock_secret_manager, mock_auth_service
    ):
        svc = ContainerService(
            provider=mock_provider,
            secret_manager=mock_secret_manager,
            auth_service=mock_auth_service,
        )
        session = await svc._validate_session_and_get("test-sid")
        assert session.session_id == "test-sid"
        mock_auth_service.validate_session.assert_awaited_once_with("test-sid")

    @pytest.mark.asyncio
    async def test_validate_session_and_get_invalid(
        self, mock_provider, mock_secret_manager, mock_auth_service
    ):
        mock_auth_service.validate_session = AsyncMock(return_value=False)
        svc = ContainerService(
            provider=mock_provider,
            secret_manager=mock_secret_manager,
            auth_service=mock_auth_service,
        )
        from backend.app.services.containers import AuthenticationError
        with pytest.raises(AuthenticationError, match="Invalid or expired session"):
            await svc._validate_session_and_get("bad-sid")

    @pytest.mark.asyncio
    async def test_list_containers_with_auth(
        self, mock_provider, mock_secret_manager, mock_auth_service
    ):
        svc = ContainerService(
            provider=mock_provider,
            secret_manager=mock_secret_manager,
            auth_service=mock_auth_service,
        )
        result = await svc.list_containers_with_auth("test-sid")
        assert result == []
        mock_auth_service.validate_session.assert_awaited_once()
```

- [ ] **Step 2: テスト実行 — 失敗確認**

Run: `cd backend && python -m pytest tests/test_container_service_auth.py -xvs 2>&1 | tail -20`
Expected: FAIL

- [ ] **Step 3: ContainerService に AuthService DI を実装 [Green]**

`backend/app/services/containers.py` のコンストラクタに `auth_service` を追加:

```python
    def __init__(
        self,
        provider: ContainerProvider,
        secret_manager: SecretManager,
        auth_service: Optional['AuthService'] = None,
        state_store: Optional[StateStore] = None,
    ):
        self.provider = provider
        self.secret_manager = secret_manager
        self.auth_service = auth_service
        self._state_store = state_store or StateStore()
```

新メソッドを `close` の前に追加:

```python
    async def _validate_session_and_get(self, session_id: str):
        """セッションを検証し取得する。"""
        if self.auth_service is None:
            raise RuntimeError("AuthService is not configured")
        is_valid = await self.auth_service.validate_session(session_id)
        if not is_valid:
            raise ValueError("Invalid or expired session")
        session = await self.auth_service.get_session(session_id)
        if session is None:
            raise ValueError("Invalid or expired session")
        return session

    async def list_containers_with_auth(self, session_id: str, all_containers: bool = True):
        """認証付きコンテナ一覧取得。"""
        await self._validate_session_and_get(session_id)
        return await self.list_containers(all_containers=all_containers)

    async def create_container_with_auth(self, config: ContainerConfig, session_id: str) -> str:
        """認証付きコンテナ作成。"""
        session = await self._validate_session_and_get(session_id)
        return await self.create_container(config=config, session_id=session_id, bw_session_key=session.bw_session_key)
```

ファイル先頭に TYPE_CHECKING import:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .auth import AuthService
```

- [ ] **Step 4: テスト実行 — 成功確認**

Run: `cd backend && python -m pytest tests/test_container_service_auth.py -xvs 2>&1 | tail -20`
Expected: PASS

- [ ] **Step 5: 回帰テスト**

Run: `cd backend && python -m pytest tests/ -x -q --tb=short 2>&1 | tail -20`
Expected: All tests PASS

- [ ] **Step 6: コミット**

```bash
git add backend/app/services/containers.py backend/tests/test_container_service_auth.py
git commit -m "feat(service): ContainerService に AuthService DI と認証付きメソッドを追加"
```

---

### Task 6: API ルーターの Thin Controller 化 [Refactor]

**Files:**
- Modify: `backend/app/api/containers.py`

- [ ] **Step 1: get_container_service に AuthService を注入**

```python
def get_container_service(
    secret_manager: Annotated[SecretManager, Depends(get_secret_manager)],
    container_provider: Annotated[ContainerProvider, Depends(get_container_provider)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> ContainerService:
    global _container_service, _state_store
    if _container_service is None:
        _state_store = StateStore()
        _state_store.init_schema()
        _container_service = ContainerService(
            container_provider,
            secret_manager,
            auth_service=auth_service,
            state_store=_state_store,
        )
    return _container_service
```

- [ ] **Step 2: list_containers エンドポイントを簡略化**

`auth_service` パラメータと手動セッション検証を削除し、`container_service.list_containers_with_auth()` を呼ぶ。`ValueError` を `401` にマッピング。

- [ ] **Step 3: `_create_container_internal` を削除し create/install を簡略化**

`create_container_with_auth()` を呼ぶ形に変更。`ValueError` → 401、`ContainerAlreadyExistsError` → 409 のマッピングは維持。

- [ ] **Step 4: start/stop/restart/delete も同パターンで簡略化**

各エンドポイントから `auth_service` Depends と手動セッション検証を削除。Service 層に認証付きメソッド（`_validate_session_and_get` を内部で呼ぶラッパー）を必要に応じて追加するか、既存メソッドを直接呼んでルーター側で `_validate_session_and_get` を使う。

- [ ] **Step 5: 全テスト実行 — Green 確認**

Run: `cd backend && python -m pytest tests/ -x -q --tb=short 2>&1 | tail -20`
Expected: All tests PASS

- [ ] **Step 6: コミット**

```bash
git add backend/app/api/containers.py
git commit -m "refactor(api): containers ルーターを Thin Controller 化"
```

---

## セルフレビューチェック

- [x] **Spec カバレッジ**: §2 DinD+TLS → Task 2-4, §3.1 Devcontainer → Task 2-3, §3.2 DI/Service → Task 5-6, §3.3 異常系 → 既存 ContainerUnavailableError + TLS 構成, §4 後方互換 → API スキーマ無変更
- [x] **プレースホルダー**: なし
- [x] **型の一貫性**: `_validate_session_and_get`, `list_containers_with_auth`, `create_container_with_auth` は全タスクで統一
