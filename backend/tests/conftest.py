from __future__ import annotations

import os
import stat
from typing import Iterator
from unittest.mock import MagicMock, patch

from hypothesis import settings

import pytest

from docker.errors import NotFound

from app.services.state_store import StateStore
from app import config as app_config

_DEFAULT_MAX_EXAMPLES = int(os.getenv("HYPOTHESIS_MAX_EXAMPLES", "25"))

# CI/コンテナ環境では I/O 初期化で 200ms を超えることがあるため、
# デッドラインを無効化してフレークを防ぐ。
if "HYPOTHESIS_PROFILE" not in os.environ:
    try:
        settings.register_profile(
            "ci",
            settings(
                deadline=None,
                max_examples=_DEFAULT_MAX_EXAMPLES,
            ),
        )
    except ValueError:
        # プロファイルが既に存在する場合は無視して既定プロファイルを読み込む
        pass
    settings.load_profile("ci")


@pytest.fixture(autouse=True)
def _mock_docker_socket(tmp_path) -> Iterator[None]:
    """
    CI 環境では Docker デーモンが無いので、Docker ソケット存在チェックをパスさせるために
    ダミーの Unix ソケットファイルパスを用意し、設定を上書きする。
    実際の接続は行わない設計のため、Docker SDK のクライアントは常にモックする。
    テスト間でモック状態が共有されないよう、function スコープで初期化する。
    個別の挙動が必要な場合はテスト側で patch して上書きする。
    """
    socket_path = tmp_path / "docker.sock"
    socket_path.touch()
    socket_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    fake_host = f"unix://{socket_path}"
    previous_env = os.environ.get("DOCKER_HOST")
    previous_setting = app_config.settings.docker_host
    os.environ["DOCKER_HOST"] = fake_host
    # ContainerService は settings を参照するため、設定オブジェクトも更新
    app_config.settings.docker_host = fake_host

    docker_client_patcher = patch("docker.DockerClient")
    docker_from_env_patcher = patch("docker.from_env")
    docker_client_mock = docker_client_patcher.start()
    docker_from_env_mock = docker_from_env_patcher.start()
    mock_client = docker_client_mock.return_value
    containers_store: list[MagicMock] = []
    container_counter = 0

    def _next_container_id() -> str:
        nonlocal container_counter
        container_counter += 1
        return f"mock-container-{container_counter}"

    def _build_container(
        name: str | None = None,
        image: str | None = None,
        status: str = "running",
        container_id: str | None = None,
    ) -> MagicMock:
        container = MagicMock()
        container.id = container_id or _next_container_id()
        container.name = name or container.id
        container.status = status
        container.image = MagicMock()
        image_tag = image or "mock-image:latest"
        container.image.tags = [image_tag]
        container.image.id = "sha256:mockimage"
        container.attrs = {
            "Created": "2024-01-01T00:00:00.000000000Z",
            "Config": {"Env": []},
            "NetworkSettings": {"Ports": {}},
        }
        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = b'{"result": {"tools": [], "resources": [], "prompts": []}}'
        container.exec_run.return_value = mock_exec_result

        def _start() -> None:
            container.status = "running"

        def _stop(*_args, **_kwargs) -> None:
            container.status = "exited"

        def _restart(*_args, **_kwargs) -> None:
            container.status = "running"

        def _remove(*_args, **_kwargs) -> None:
            if container in containers_store:
                containers_store.remove(container)

        container.start.side_effect = _start
        container.stop.side_effect = _stop
        container.restart.side_effect = _restart
        container.remove.side_effect = _remove
        return container

    def _append_container(
        name: str | None = None,
        image: str | None = None,
        status: str = "running",
        container_id: str | None = None,
    ) -> MagicMock:
        container = _build_container(
            name=name, image=image, status=status, container_id=container_id
        )
        containers_store.append(container)
        return container

    _append_container(
        name="mock-container",
        image="mock-image:latest",
        status="running",
        container_id="mock-container-id",
    )

    mock_image = MagicMock()
    mock_image.id = "sha256:mockimage"
    mock_image.tags = ["mock-image:latest"]
    mock_image.attrs = {"RepoTags": ["mock-image:latest"]}

    mock_client.containers = MagicMock()

    def _create_container(*args, **kwargs) -> MagicMock:
        image = kwargs.get("image") or (args[0] if args else None)
        name = kwargs.get("name")
        return _append_container(name=name, image=image, status="created")

    def _run_container(*args, **kwargs) -> MagicMock:
        image = kwargs.get("image") or (args[0] if args else None)
        name = kwargs.get("name")
        return _append_container(name=name, image=image, status="running")

    def _list_containers(*_args, **kwargs) -> list[MagicMock]:
        filters = kwargs.get("filters") or {}
        name_filter = filters.get("name")
        if name_filter:
            pattern = str(name_filter)
            if pattern.startswith("^") and pattern.endswith("$"):
                target = pattern[1:-1]
                return [c for c in containers_store if c.name == target]
            return [c for c in containers_store if pattern in c.name]
        return list(containers_store)

    def _get_container(container_id: str) -> MagicMock:
        lookup = str(container_id)
        for container in containers_store:
            if container.id == lookup or container.name == lookup:
                return container
            if lookup.startswith("/") and f"/{container.name}" == lookup:
                return container
        raise NotFound(f"Container not found: {lookup}")

    mock_client.containers.create.side_effect = _create_container
    mock_client.containers.run.side_effect = _run_container
    mock_client.containers.list.side_effect = _list_containers
    mock_client.containers.get.side_effect = _get_container

    mock_client.images = MagicMock()
    mock_client.images.get.return_value = mock_image
    mock_client.images.pull.return_value = mock_image
    mock_client.images.list.return_value = [mock_image]

    mock_client.api = MagicMock()
    mock_client.api.containers.return_value = [
        {
            "Id": "mock-container-id",
            "Names": ["/mock-container"],
            "Image": "mock-image:latest",
            "State": "running",
            "Status": "Up 5 seconds",
            "Created": 1700000000,
            "Ports": [{"PrivatePort": 8080, "PublicPort": 18080}],
            "Labels": {"mcp.server": "mock"},
        }
    ]
    mock_client.ping.return_value = True
    mock_client.close.return_value = None
    docker_from_env_mock.return_value = mock_client

    try:
        yield
    finally:
        docker_from_env_patcher.stop()
        docker_client_patcher.stop()
        if previous_env is None:
            os.environ.pop("DOCKER_HOST", None)
        else:
            os.environ["DOCKER_HOST"] = previous_env
        app_config.settings.docker_host = previous_setting


@pytest.fixture(autouse=True)
def clear_auth_sessions() -> None:
    """各テスト間で認証セッションの永続データをクリーンに保つ。"""
    try:
        from app.services import auth as auth_service  # pylint: disable=import-outside-toplevel

        if hasattr(auth_service, "_INITIALIZED_DB_PATHS"):
            auth_service._INITIALIZED_DB_PATHS.clear()
    except Exception:
        pass
    store = StateStore()
    store.init_schema()
    try:
        with store._connect() as conn:  # type: ignore[attr-defined]
            conn.execute("DELETE FROM auth_sessions")
            conn.commit()
    except Exception:
        # DB がまだ初期化されていない場合などはスキップ
        return
    finally:
        try:
            from app.services import auth as auth_service  # pylint: disable=import-outside-toplevel

            if hasattr(auth_service, "_INITIALIZED_DB_PATHS"):
                auth_service._INITIALIZED_DB_PATHS.clear()
        except Exception:
            pass
