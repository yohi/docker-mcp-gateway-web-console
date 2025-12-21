from __future__ import annotations

import os
import stat
from typing import Iterator
from unittest.mock import patch

from hypothesis import settings

import pytest

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


@pytest.fixture(scope="session", autouse=True)
def _mock_docker_socket(tmp_path_factory) -> Iterator[None]:
    """
    CI 環境では Docker デーモンが無いので、Docker ソケット存在チェックをパスさせるために
    ダミーの Unix ソケットファイルパスを用意し、設定を上書きする。
    実際の接続は行わない設計のため、Docker SDK のクライアントは常にモックする。
    """
    socket_dir = tmp_path_factory.mktemp("docker-socket")
    socket_path = socket_dir / "docker.sock"
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
